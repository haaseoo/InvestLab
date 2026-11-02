"""한국투자증권 LIVE Provider(조회 전용).

- 국내 잔고(TTTC8434R)와 해외 체결기준현재잔고(CTRP6504R) 두 번의 조회로 보유 종목, 현재가,
  평가금액, 환율, 예수금을 모두 얻는다. 별도 시세 API는 부르지 않는다.
- 하나라도 실패하면 전체를 오류로 돌려준다. 일부 잔고만으로 총액을 보여 주지 않고,
  Mock으로 대체하지도 않는다.
- 같은 화면이 여러 API를 동시에 부르므로 결과를 짧게(30초) 공유해 KIS 호출 수를 줄인다.
- KIS 잔고 응답에는 시세 시각이 없다. 조회 시각을 기준 시각으로 쓴다. 장이 닫혀 있으면
  현재가는 마지막 체결가다.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.core.config import Settings
from app.core.errors import KisNotConfiguredError
from app.core.logging import mask_account
from app.integrations.kis.classification import Classification, load_classifications
from app.integrations.kis.client import KisClient
from app.integrations.kis.master import OverseasMaster, SecurityKind
from app.integrations.kis.parse import KisFx, KisHolding, parse_domestic, parse_overseas
from app.providers.base import PortfolioProvider
from app.schemas.analysis import EtfComposition
from app.schemas.portfolio import (
    AccountSummary,
    AssetClass,
    AssetType,
    FxRate,
    Holding,
    Position,
    ProviderCheck,
    ProviderStatus,
    Quote,
    SnapshotPoint,
    Source,
)
from app.services.valuation import build_holding

logger = logging.getLogger("investlab.kis")

DOMESTIC_BALANCE = "/uapi/domestic-stock/v1/trading/inquire-balance"
OVERSEAS_BALANCE = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
DOMESTIC_INFO = "/uapi/domestic-stock/v1/quotations/search-stock-info"
CACHE_SECONDS = 30.0
VALUATION_BASE = "KRW"

# 국내 상품기본조회(CTPF1002R)의 증권그룹ID. 공식 종목마스터 정의(ST:주권, EF:ETF)와 같고,
# 2026-11-02 공개 종목(005930=ST, 069500=EF)으로 확인했다.
DOMESTIC_GROUP_KIND = {"ST": SecurityKind.STOCK, "EF": SecurityKind.ETF}


def parse_account(value: str) -> tuple[str, str]:
    match = re.fullmatch(r"(\d{8})-?(\d{2})", value.strip())
    if not match:
        raise KisNotConfiguredError("KIS 계좌번호 형식이 올바르지 않습니다(8자리-2자리).")
    return match.group(1), match.group(2)


@dataclass(frozen=True)
class LiveData:
    holdings: list[KisHolding]
    kinds: dict[tuple[str, str], str | None]
    fx: list[KisFx]
    cash: dict[str, Decimal]
    retrieved_at: datetime


class KISPortfolioProvider(PortfolioProvider):
    source = Source.LIVE
    is_demo = False

    def __init__(
        self,
        settings: Settings,
        auth_available: bool = False,
        database_available: bool = False,
        client: KisClient | None = None,
        master: OverseasMaster | None = None,
    ):
        self._settings = settings
        self._auth_available = auth_available
        self._database_available = database_available
        self._client = client
        self._master = master
        self._lock = asyncio.Lock()
        self._cached: LiveData | None = None
        self._domestic_kinds: dict[str, str | None] = {}

    # --- 설정 ---

    @property
    def configured(self) -> bool:
        s = self._settings
        return bool(s.kis_app_key and s.kis_app_secret and s.kis_account_no)

    def _account(self) -> tuple[str, str]:
        if not self._settings.kis_account_no:
            raise KisNotConfiguredError()
        return parse_account(self._settings.kis_account_no.get_secret_value())

    def _get_client(self) -> KisClient:
        if self._client is None:
            s = self._settings
            if not (s.kis_app_key and s.kis_app_secret):
                raise KisNotConfiguredError()
            self._client = KisClient(
                s.kis_app_key.get_secret_value(),
                s.kis_app_secret.get_secret_value(),
                s.kis_token_cache_path,
            )
        return self._client

    def _get_master(self) -> OverseasMaster:
        if self._master is None:
            self._master = OverseasMaster(self._settings.kis_token_cache_path.parent / "kis_master")
        return self._master

    # --- 조회 ---

    async def _load(self) -> LiveData:
        async with self._lock:
            now = datetime.now(UTC)
            if (
                self._cached is not None
                and (now - self._cached.retrieved_at).total_seconds() < CACHE_SECONDS
            ):
                return self._cached
            self._cached = await self._fetch()
            return self._cached

    async def _fetch(self) -> LiveData:
        if not self.configured:
            raise KisNotConfiguredError()
        cano, product = self._account()
        client = self._get_client()

        domestic_pages = await client.get_pages(
            DOMESTIC_BALANCE,
            "TTTC8434R",
            {
                "CANO": cano,
                "ACNT_PRDT_CD": product,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",  # 종목별(대출일별로 나뉘지 않게)
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",  # 전일매매 포함
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
            "ctx_area_fk100",
            "ctx_area_nk100",
        )
        overseas = await client.get(
            OVERSEAS_BALANCE,
            "CTRP6504R",
            {
                "CANO": cano,
                "ACNT_PRDT_CD": product,
                "WCRC_FRCR_DVSN_CD": "02",  # 외화 기준
                "NATN_CD": "000",  # 전체 국가
                "TR_MKET_CD": "00",
                "INQR_DVSN_CD": "00",
            },
        )
        retrieved_at = datetime.now(UTC)

        domestic, krw_cash = parse_domestic(domestic_pages)
        foreign, fx, foreign_cash = parse_overseas(overseas.body)
        cash = dict(foreign_cash)
        if krw_cash is not None:
            cash["KRW"] = krw_cash

        holdings = domestic + foreign
        kinds = {(h.market, h.symbol): await self._kind(h) for h in holdings}
        return LiveData(holdings, kinds, fx, cash, retrieved_at)

    async def _kind(self, h: KisHolding) -> str | None:
        """판별에 실패하면 None(알 수 없음)이다. 주식으로 가정하지 않는다."""
        if not h.domestic:
            return await self._get_master().kind(h.exchange_code, h.symbol)
        if h.symbol in self._domestic_kinds:
            return self._domestic_kinds[h.symbol]
        try:
            res = await self._get_client().get(
                DOMESTIC_INFO, "CTPF1002R", {"PRDT_TYPE_CD": "300", "PDNO": h.symbol}
            )
            output = res.body.get("output") or {}
            group = output.get("scty_grp_id_cd") if isinstance(output, dict) else None
            kind = DOMESTIC_GROUP_KIND.get(group or "", SecurityKind.OTHER if group else None)
        except Exception as exc:  # noqa: BLE001 - 분류 실패가 잔고 조회를 막지 않게 한다
            logger.warning("KIS domestic classification failed: %s", type(exc).__name__)
            return None
        self._domestic_kinds[h.symbol] = kind
        return kind

    def _position(
        self, h: KisHolding, kind: str | None, overrides: dict[str, Classification]
    ) -> Position:
        if kind == SecurityKind.STOCK:
            asset_type = AssetType.STOCK
            asset_class = AssetClass.DOMESTIC_STOCK if h.domestic else AssetClass.OVERSEAS_STOCK
            exposure = h.country
        elif kind == SecurityKind.ETF:
            asset_type, asset_class, exposure = AssetType.ETF, AssetClass.ETF_UNCLASSIFIED, None
        else:
            asset_type, asset_class, exposure = AssetType.OTHER, AssetClass.OTHER, None

        override = overrides.get(h.symbol)
        return Position(
            symbol=h.symbol,
            market=h.market,
            asset_type=asset_type,
            asset_class=(
                override.asset_class if override and override.asset_class else asset_class
            ),
            name=h.name,
            quantity=h.quantity,
            average_cost=h.average_cost,
            currency=h.currency,
            country=h.country,
            exposure_country=(
                override.exposure_country if override and override.exposure_country else exposure
            ),
            sector=override.sector if override else None,
            benchmark=override.benchmark if override else None,
        )

    def _fx_rates(self, data: LiveData) -> list[FxRate]:
        return [
            FxRate(
                base_currency=f.currency,
                quote_currency=VALUATION_BASE,
                rate=f.rate,
                as_of=data.retrieved_at,
                source=self.source,
            )
            for f in data.fx
        ]

    def _quote(self, h: KisHolding, data: LiveData) -> Quote:
        return Quote(
            symbol=h.symbol,
            market=h.market,
            price=h.price,
            currency=h.currency,
            as_of=data.retrieved_at if h.price is not None else None,
            source=self.source,
            is_demo=False,
        )

    async def get_holdings(self, valuation_currency: str) -> list[Holding]:
        data = await self._load()
        overrides = load_classifications(self._settings.live_classification_file)
        fx_rates = self._fx_rates(data)
        return [
            build_holding(
                position=self._position(h, data.kinds.get((h.market, h.symbol)), overrides),
                quote=self._quote(h, data),
                fx_rates=fx_rates,
                valuation_currency=valuation_currency,
                source=self.source,
                is_demo=False,
                reported_market_value=h.reported_value,
            )
            for h in data.holdings
        ]

    async def get_quotes(self, symbols: list[str] | None = None) -> list[Quote]:
        data = await self._load()
        return [
            self._quote(h, data) for h in data.holdings if symbols is None or h.symbol in symbols
        ]

    async def get_fx_rates(self) -> list[FxRate]:
        return self._fx_rates(await self._load())

    async def get_account_summary(self) -> AccountSummary:
        data = await self._load()
        cano, product = self._account()
        return AccountSummary(
            account_masked=mask_account(cano + product),
            cash_balances=data.cash or None,
            as_of=data.retrieved_at,
            source=self.source,
            is_demo=False,
        )

    async def get_history(self) -> list[SnapshotPoint]:
        # 실제 계좌 이력은 KIS가 아니라 사용자가 저장한 스냅샷(DB)에서 온다. 라우터가 처리한다.
        return []

    async def get_etf_compositions(self) -> list[EtfComposition]:
        # 확인된 ETF 구성 종목 데이터 출처가 없다. 비워 두면 중복 분석은 "데이터 없음"으로 표시된다.
        return []

    def get_provider_status(self) -> ProviderStatus:
        s = self._settings
        account_ok = False
        if s.kis_account_no:
            try:
                parse_account(s.kis_account_no.get_secret_value())
                account_ok = True
            except KisNotConfiguredError:
                account_ok = False
        checks = [
            ProviderCheck(
                key="kis_credentials",
                label="KIS App Key·Secret 설정",
                ok=bool(s.kis_app_key and s.kis_app_secret),
            ),
            ProviderCheck(key="kis_account", label="KIS 계좌번호 설정", ok=account_ok),
            ProviderCheck(key="auth", label="사용자 인증(Supabase) 연결", ok=self._auth_available),
            ProviderCheck(
                key="database", label="스냅샷 저장소(DB) 연결", ok=self._database_available
            ),
            ProviderCheck(
                key="owner", label="LIVE 계좌 소유자 지정", ok=bool(s.live_owner_user_id)
            ),
        ]
        required = {"kis_credentials", "kis_account", "auth", "owner"}
        ready = all(c.ok for c in checks if c.key in required)
        return ProviderStatus(
            source=self.source,
            state="ready" if ready else "not_configured",
            is_demo=False,
            label="LIVE",
            message=(
                "한국투자증권 계좌를 조회 전용으로 연결합니다. 소유자로 로그인하면 볼 수 있습니다."
                if ready
                else "한국투자증권 연결에 필요한 설정이 빠져 있습니다."
            ),
            checks=checks,
        )
