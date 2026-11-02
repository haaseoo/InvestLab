"""PortfolioProvider 공통 인터페이스. 구현체는 모두 같은 내부 모델을 반환한다."""

from abc import ABC, abstractmethod

from app.schemas.portfolio import (
    AccountSummary,
    FxRate,
    Holding,
    ProviderStatus,
    Quote,
    SnapshotPoint,
    Source,
)


class PortfolioProvider(ABC):
    source: Source
    is_demo: bool

    @abstractmethod
    async def get_holdings(self, valuation_currency: str) -> list[Holding]: ...

    @abstractmethod
    async def get_account_summary(self) -> AccountSummary: ...

    @abstractmethod
    async def get_quotes(self, symbols: list[str] | None = None) -> list[Quote]: ...

    @abstractmethod
    async def get_fx_rates(self) -> list[FxRate]: ...

    @abstractmethod
    async def get_history(self) -> list[SnapshotPoint]: ...

    @abstractmethod
    def get_provider_status(self) -> ProviderStatus:
        """외부 호출 없이 판단한다. 값이 아니라 설정 여부만 담아 비밀이 노출되지 않게 한다."""
