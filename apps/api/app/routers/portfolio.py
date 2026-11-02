from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from starlette.concurrency import run_in_threadpool

from app.core.errors import DatabaseNotConfiguredError
from app.db import repositories as repo
from app.routers.deps import ProviderDep, SettingsDep
from app.schemas.portfolio import (
    AllocationResponse,
    HistoryResponse,
    HoldingsResponse,
    PortfolioResponse,
    ProvidersStatusResponse,
    SnapshotPoint,
    Source,
    SummaryResponse,
)
from app.services import portfolio as service

router = APIRouter(prefix="/api/v1")
HISTORY_LIMIT = 100


@router.get("/providers/status", response_model=ProvidersStatusResponse)
async def providers_status(request: Request) -> ProvidersStatusResponse:
    providers = request.app.state.providers
    return ProvidersStatusResponse(
        default_source=Source.MOCK,
        providers=[p.get_provider_status() for p in providers.values()],
    )


@router.get("/portfolio", response_model=PortfolioResponse)
async def portfolio(provider: ProviderDep, settings: SettingsDep) -> PortfolioResponse:
    return await service.get_portfolio(provider, settings.valuation_currency)


@router.get("/portfolio/holdings", response_model=HoldingsResponse)
async def holdings(provider: ProviderDep, settings: SettingsDep) -> HoldingsResponse:
    return await service.get_holdings(provider, settings.valuation_currency)


@router.get("/portfolio/summary", response_model=SummaryResponse)
async def summary(provider: ProviderDep, settings: SettingsDep) -> SummaryResponse:
    return await service.get_summary(provider, settings.valuation_currency)


@router.get("/portfolio/history", response_model=HistoryResponse)
async def history(
    request: Request, provider: ProviderDep, settings: SettingsDep
) -> HistoryResponse:
    if provider.source is Source.LIVE:
        points = await _live_history(request, settings.valuation_currency)
    else:
        points = await provider.get_history()
    return HistoryResponse(
        source=provider.source,
        is_demo=provider.is_demo,
        retrieved_at=datetime.now(UTC),
        points=points,
    )


async def _live_history(request: Request, currency: str) -> list[SnapshotPoint]:
    """실제 계좌 이력 = 소유자가 저장한 스냅샷. 가상 이력을 만들지 않는다.

    평가하지 못한 종목이 있는(불완전한) 스냅샷은 총액이 실제보다 작으므로 선에 넣지 않는다.
    """
    db = request.app.state.db
    if db is None:
        raise DatabaseNotConfiguredError()
    user = request.state.live_user

    def run():
        with db.user_transaction(user) as conn:
            return repo.list_snapshots(conn, HISTORY_LIMIT)

    snapshots = await run_in_threadpool(run)
    return [
        SnapshotPoint(
            captured_at=s.as_of,
            total_market_value=s.total_market_value,
            total_cost_basis=s.total_cost_basis,
            valuation_currency=s.valuation_currency,
        )
        for s in sorted(snapshots, key=lambda s: s.as_of)
        if s.is_complete and s.source is Source.LIVE and s.valuation_currency == currency
    ]


@router.get("/analytics/allocation", response_model=AllocationResponse)
async def allocation(
    provider: ProviderDep,
    settings: SettingsDep,
    dimension: Annotated[
        Literal["asset_class", "asset_type", "market", "currency", "exposure_country", "sector"],
        Query(),
    ] = "asset_class",
) -> AllocationResponse:
    return await service.get_allocation(provider, settings.valuation_currency, dimension)
