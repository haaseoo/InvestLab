"""시뮬레이션 API. 계산만 하고 저장하지 않는다(저장은 Phase 3). 주문을 실행하지 않는다."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from starlette.concurrency import run_in_threadpool

from app.core.security import require_live_owner
from app.db import repositories as repo
from app.providers.base import PortfolioProvider
from app.routers.deps import DatabaseDep, ProviderDep, SettingsDep, UserDep
from app.schemas.analysis import (
    BuyRequest,
    BuyResponse,
    RebalanceRequest,
    RebalanceResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from app.schemas.portfolio import Holding, Source
from app.schemas.user_data import (
    SimulationHistoryCreate,
    SimulationHistoryItem,
    SimulationHistoryResponse,
)
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


# ---------------------------------------------------------------- 기록 (로그인 필요)


@router.get("/history", response_model=SimulationHistoryResponse)
async def list_history(
    user: UserDep, db: DatabaseDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> SimulationHistoryResponse:
    def run():
        with db.user_transaction(user) as conn:
            return SimulationHistoryResponse(items=repo.list_simulations(conn, limit))

    return await run_in_threadpool(run)


@router.post("/history", response_model=SimulationHistoryItem, status_code=status.HTTP_201_CREATED)
async def save_history(
    body: SimulationHistoryCreate, user: UserDep, db: DatabaseDep, settings: SettingsDep
) -> SimulationHistoryItem:
    # LIVE 데이터로 만든 결과는 LIVE 소유자만 저장할 수 있다. Mock 결과는 DEMO로 표시되어 저장된다.
    if body.source is Source.LIVE:
        require_live_owner(user, settings.live_owner_user_id)

    def run():
        with db.user_transaction(user) as conn:
            return repo.insert_simulation(conn, body)

    return await run_in_threadpool(run)


@router.delete("/history/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(item_id: str, user: UserDep, db: DatabaseDep) -> Response:
    import uuid

    from app.core.errors import NotFoundError

    try:
        uuid.UUID(item_id)
    except ValueError as exc:
        raise NotFoundError() from exc

    def run():
        with db.user_transaction(user) as conn:
            repo.delete_simulation(conn, item_id)

    await run_in_threadpool(run)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
