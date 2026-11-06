"""한국투자증권 LIVE Provider(조회 전용). 인스턴스 하나가 사용자 한 명의 계좌 하나를 맡는다.

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
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from app.integrations.kis.classification import Classification, load_classifications
from app.integrations.kis.client import KisClient
from app.integrations.kis.credentials import KisCredentials
from app.integrations.kis.gics import SYMBOL_SECTOR, sector_for_industry
from app.integrations.kis.industry import OverseasIndustries
from app.integrations.kis.master import EXCHANGE_MASTER, US_MASTERS, SecurityKind
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


@dataclass(frozen=True)
class LiveData:
    holdings: list[KisHolding]
    kinds: dict[tuple[str, str], str | None]
    sectors: dict[tuple[str, str], str | None]
    fx: list[KisFx]
    cash: dict[str, Decimal]
    retrieved_at: datetime


class KISPortfolioProvider(PortfolioProvider):
    source = Source.LIVE
    is_demo = False

    def __init__(
        self,
        credentials: KisCredentials,
        client: KisClient,
        master: "MasterLookup",
        classification_file: Path,
        industries: OverseasIndustries | None = None,
    ):
        self.credentials = credentials
        self._client = client
        self._master = master
        self._classification_file = classification_file
        self._industries = industries
        self._lock = asyncio.Lock()
        self._cached: LiveData | None = None
        self._domestic_kinds: dict[str, str | None] = {}

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
        cano, product = self.credentials.cano, self.credentials.product
        client = self._client

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
        sectors = {
            (h.market, h.symbol): await self._sector(h, kinds[(h.market, h.symbol)])
            for h in holdings
        }
        return LiveData(holdings, kinds, sectors, fx, cash, retrieved_at)

    async def _sector(self, h: KisHolding, kind: str | None) -> str | None:
        """해외 개별주만. 마스터 파일의 업종분류코드 → KIS 업종명 → GICS 섹터. 모르면 None."""
        if h.domestic or kind != SecurityKind.STOCK:
            return None
        if EXCHANGE_MASTER.get(h.exchange_code) in US_MASTERS and h.symbol in SYMBOL_SECTOR:
            return SYMBOL_SECTOR[h.symbol]
        if self._industries is None:
            return None
        try:
            found = await self._master.sector_code(h.exchange_code, h.symbol)
            if found is None:
                return None
            exchange, code = found
            return sector_for_industry(await self._industries.name(self._client, exchange, code))
        except Exception as exc:  # noqa: BLE001 - 섹터 실패가 잔고 조회를 막지 않게 한다
            logger.warning("KIS sector lookup failed: %s", type(exc).__name__)
            return None

    async def _kind(self, h: KisHolding) -> str | None:
        """판별에 실패하면 None(알 수 없음)이다. 주식으로 가정하지 않는다."""
        if not h.domestic:
            return await self._master.kind(h.exchange_code, h.symbol)
        if h.symbol in self._domestic_kinds:
            return self._domestic_kinds[h.symbol]
        try:
            res = await self._client.get(
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
        self,
        h: KisHolding,
        kind: str | None,
        sector: str | None,
        overrides: dict[str, Classification],
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
            # 사용자가 분류 파일에 지정한 섹터가 KIS 업종명보다 우선한다.
            sector=override.sector if override and override.sector else sector,
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
        overrides = load_classifications(self._classification_file)
        fx_rates = self._fx_rates(data)
        return [
            build_holding(
                position=self._position(
                    h,
                    data.kinds.get((h.market, h.symbol)),
                    data.sectors.get((h.market, h.symbol)),
                    overrides,
                ),
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
        return AccountSummary(
            account_masked=self.credentials.account_masked,
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
        return live_provider_status(True, True, True)


class MasterLookup(Protocol):
    async def kind(self, exchange: str, symbol: str) -> str | None: ...

    async def sector_code(self, exchange: str, symbol: str) -> tuple[str, str] | None: ...


def live_provider_status(
    auth_available: bool, database_available: bool, credential_store_available: bool
) -> ProviderStatus:
    """서버 쪽 LIVE 준비 상태. 사용자별 키 등록 여부는 /kis/credentials에서 따로 확인한다."""
    checks = [
        ProviderCheck(key="auth", label="사용자 인증(Supabase) 연결", ok=auth_available),
        ProviderCheck(key="database", label="데이터베이스 연결", ok=database_available),
        ProviderCheck(
            key="credential_store",
            label="키 암호화 설정(KIS_CREDENTIAL_KEY)",
            ok=credential_store_available,
        ),
    ]
    ready = all(c.ok for c in checks)
    return ProviderStatus(
        source=Source.LIVE,
        state="ready" if ready else "not_configured",
        is_demo=False,
        label="LIVE",
        message=(
            "로그인한 뒤 설정에서 본인의 한국투자증권 App Key·Secret·계좌번호를 등록하면 "
            "본인 계좌를 조회 전용으로 볼 수 있습니다."
            if ready
            else "서버에 LIVE 조회에 필요한 설정이 빠져 있습니다."
        ),
        checks=checks,
    )
