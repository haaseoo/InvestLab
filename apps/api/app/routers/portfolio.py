from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request

from app.routers.deps import ProviderDep, SettingsDep
from app.schemas.portfolio import (
    AllocationResponse,
    HistoryResponse,
    HoldingsResponse,
    PortfolioResponse,
    ProvidersStatusResponse,
    Source,
    SummaryResponse,
)
from app.services import portfolio as service

router = APIRouter(prefix="/api/v1")


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
async def history(provider: ProviderDep) -> HistoryResponse:
    return HistoryResponse(
        source=provider.source,
        is_demo=provider.is_demo,
        retrieved_at=datetime.now(UTC),
        points=await provider.get_history(),
    )


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
