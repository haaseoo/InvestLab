from fastapi import APIRouter

from app.routers.deps import ProviderDep, SettingsDep
from app.schemas.analysis import RiskResponse
from app.services.risk import get_risk

router = APIRouter(prefix="/api/v1/analytics")


@router.get("/risk", response_model=RiskResponse)
async def risk(provider: ProviderDep, settings: SettingsDep) -> RiskResponse:
    return await get_risk(provider, settings.valuation_currency)
