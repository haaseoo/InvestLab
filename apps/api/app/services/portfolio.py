"""Provider 데이터를 API 응답으로 조립한다. Provider 종류에 따라 분기하지 않는다."""

from datetime import UTC, datetime

from app.providers.base import PortfolioProvider
from app.schemas.portfolio import (
    AllocationResponse,
    Holding,
    HoldingsResponse,
    PortfolioResponse,
    ResponseMeta,
    SummaryResponse,
)
from app.services.analytics import (
    ASSUMPTIONS,
    apply_weights,
    compute_allocation,
    compute_concentration,
    compute_summary,
)


def _meta(provider: PortfolioProvider, holdings: list[Holding], valuation_currency: str) -> dict:
    # 가장 오래된 시세 시각을 기준 시점으로 삼는다. 전체가 그 시각 이후의 값이라는 뜻이다.
    timestamps = [h.as_of for h in holdings if h.as_of is not None]
    return ResponseMeta(
        source=provider.source,
        is_demo=provider.is_demo,
        as_of=min(timestamps) if timestamps else None,
        retrieved_at=datetime.now(UTC),
        valuation_currency=valuation_currency,
    ).model_dump()


async def _weighted_holdings(provider: PortfolioProvider, currency: str) -> list[Holding]:
    return apply_weights(await provider.get_holdings(currency))


async def get_holdings(provider: PortfolioProvider, currency: str) -> HoldingsResponse:
    holdings = await _weighted_holdings(provider, currency)
    return HoldingsResponse(**_meta(provider, holdings, currency), holdings=holdings)


async def get_summary(provider: PortfolioProvider, currency: str) -> SummaryResponse:
    holdings = await _weighted_holdings(provider, currency)
    return SummaryResponse(
        **_meta(provider, holdings, currency),
        summary=compute_summary(holdings, currency),
        concentration=compute_concentration(holdings),
        assumptions=ASSUMPTIONS,
    )


async def get_allocation(
    provider: PortfolioProvider, currency: str, dimension: str
) -> AllocationResponse:
    holdings = await _weighted_holdings(provider, currency)
    return AllocationResponse(
        **_meta(provider, holdings, currency),
        dimension=dimension,
        slices=compute_allocation(holdings, dimension),
        excluded_symbols=[h.symbol for h in holdings if h.market_value_valuation is None],
    )


async def get_portfolio(provider: PortfolioProvider, currency: str) -> PortfolioResponse:
    holdings = await _weighted_holdings(provider, currency)
    return PortfolioResponse(
        **_meta(provider, holdings, currency),
        summary=compute_summary(holdings, currency),
        concentration=compute_concentration(holdings),
        assumptions=ASSUMPTIONS,
        fx_rates=await provider.get_fx_rates(),
        holdings=holdings,
        allocation=compute_allocation(holdings, "asset_class"),
    )
