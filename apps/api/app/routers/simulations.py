"""시뮬레이션 API. 계산만 하고 저장하지 않는다(저장은 Phase 3). 주문을 실행하지 않는다."""

from fastapi import APIRouter

from app.providers.base import PortfolioProvider
from app.routers.deps import ProviderDep, SettingsDep
from app.schemas.analysis import (
    BuyRequest,
    BuyResponse,
    RebalanceRequest,
    RebalanceResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from app.schemas.portfolio import Holding
from app.services import simulations
from app.services.analytics import apply_weights
from app.services.portfolio import build_meta

router = APIRouter(prefix="/api/v1/simulations")


async def _load(provider: PortfolioProvider, currency: str) -> tuple[list[Holding], dict]:
    holdings = apply_weights(await provider.get_holdings(currency))
    return holdings, build_meta(provider, holdings, currency)


@router.post("/buy", response_model=BuyResponse)
async def buy(request: BuyRequest, provider: ProviderDep, settings: SettingsDep) -> BuyResponse:
    currency = settings.valuation_currency
    holdings, meta = await _load(provider, currency)
    return BuyResponse(**meta, **simulations.simulate_buy(holdings, request, currency))


@router.post("/rebalance", response_model=RebalanceResponse)
async def rebalance(
    request: RebalanceRequest, provider: ProviderDep, settings: SettingsDep
) -> RebalanceResponse:
    holdings, meta = await _load(provider, settings.valuation_currency)
    return RebalanceResponse(**meta, **simulations.simulate_rebalance(holdings, request))


@router.post("/scenario", response_model=ScenarioResponse)
async def scenario(
    request: ScenarioRequest, provider: ProviderDep, settings: SettingsDep
) -> ScenarioResponse:
    currency = settings.valuation_currency
    holdings, meta = await _load(provider, currency)
    return ScenarioResponse(**meta, **simulations.simulate_scenario(holdings, request, currency))
