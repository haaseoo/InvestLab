"""한국투자증권 Provider 자리. 실제 호출은 Phase 4에서 구현한다.

데이터 메서드는 값을 지어내지 않고 항상 오류를 낸다. Mock으로 대체하지도 않는다.
"""

from app.core.config import Settings
from app.core.errors import LiveNotImplementedError
from app.providers.base import PortfolioProvider
from app.schemas.analysis import EtfComposition
from app.schemas.portfolio import (
    AccountSummary,
    FxRate,
    Holding,
    ProviderCheck,
    ProviderStatus,
    Quote,
    SnapshotPoint,
    Source,
)


class KISPortfolioProvider(PortfolioProvider):
    source = Source.LIVE
    is_demo = False

    def __init__(self, settings: Settings, auth_available: bool = False):
        self._settings = settings
        self._auth_available = auth_available

    async def get_holdings(self, valuation_currency: str) -> list[Holding]:
        raise LiveNotImplementedError()

    async def get_account_summary(self) -> AccountSummary:
        raise LiveNotImplementedError()

    async def get_quotes(self, symbols: list[str] | None = None) -> list[Quote]:
        raise LiveNotImplementedError()

    async def get_fx_rates(self) -> list[FxRate]:
        raise LiveNotImplementedError()

    async def get_history(self) -> list[SnapshotPoint]:
        raise LiveNotImplementedError()

    async def get_etf_compositions(self) -> list[EtfComposition]:
        # KIS가 ETF 구성 종목을 제공하는지는 Phase 4에서 공식 문서로 확인한다.
        raise LiveNotImplementedError()

    def get_provider_status(self) -> ProviderStatus:
        s = self._settings
        checks = [
            ProviderCheck(
                key="kis_credentials",
                label="KIS App Key·Secret 설정",
                ok=bool(s.kis_app_key and s.kis_app_secret),
            ),
            ProviderCheck(key="kis_account", label="KIS 계좌 설정", ok=bool(s.kis_account_no)),
            ProviderCheck(key="auth", label="사용자 인증(Supabase) 연결", ok=self._auth_available),
            ProviderCheck(
                key="owner", label="LIVE 계좌 소유자 지정", ok=bool(s.live_owner_user_id)
            ),
            ProviderCheck(key="adapter", label="KIS 연동 구현 (Phase 4)", ok=False),
        ]
        return ProviderStatus(
            source=self.source,
            state="not_implemented",
            is_demo=False,
            label="LIVE",
            message="실제 계좌가 연결되어 있지 않습니다. 한국투자증권 연동은 Phase 4에서 구현합니다.",
            checks=checks,
        )
