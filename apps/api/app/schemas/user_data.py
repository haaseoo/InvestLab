"""로그인 사용자 데이터 모델: 계정, 설정, 포트폴리오 스냅샷, 시뮬레이션 기록."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.schemas.portfolio import CurrencyCode, Exact, FxRate, Money, Source

MAX_JSON_BYTES = 256 * 1024


class MeResponse(BaseModel):
    user_id: str
    email: str | None
    database_available: bool


class KisCredentialsInput(BaseModel):
    """요청 본문. 값은 응답·로그에 다시 싣지 않는다."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    app_key: SecretStr = Field(max_length=128)
    app_secret: SecretStr = Field(max_length=1024)
    account_no: SecretStr = Field(max_length=32)


class KisCredentialsStatus(BaseModel):
    registered: bool
    account_masked: str | None = None
    updated_at: datetime | None = None


class UserSettings(BaseModel):
    theme: Literal["light", "dark", "system"] = "light"
    preferred_currency: CurrencyCode = "KRW"
    preferred_source: Source = Source.MOCK
    mask_account_numbers: bool = True


class UserSettingsResponse(UserSettings):
    updated_at: datetime | None


class SnapshotHolding(BaseModel):
    symbol: str
    market: str
    name: str
    asset_type: str
    quantity: Exact
    average_cost: Exact
    current_price: Exact | None
    currency: CurrencyCode
    cost_basis: Money
    market_value: Money | None
    fx_rate: Exact | None
    cost_basis_valuation: Money | None
    market_value_valuation: Money | None
    valuation_status: str


class SnapshotRecord(BaseModel):
    """DB에 저장하기 직전의 검증된 스냅샷."""

    source: Source
    valuation_currency: CurrencyCode
    total_market_value: Money
    total_cost_basis: Money
    holding_count: int
    valued_holding_count: int
    is_complete: bool
    fx_rates: list[FxRate]
    as_of: datetime
    content_hash: str
    holdings: list[SnapshotHolding]


class SnapshotSummary(BaseModel):
    id: str
    source: Source
    valuation_currency: CurrencyCode
    total_market_value: Money
    total_cost_basis: Money
    holding_count: int
    valued_holding_count: int
    is_complete: bool
    as_of: datetime
    captured_at: datetime


class SnapshotDetail(SnapshotSummary):
    fx_rates: list[dict[str, Any]]
    content_hash: str
    holdings: list[SnapshotHolding]


class SnapshotListResponse(BaseModel):
    snapshots: list[SnapshotSummary]


class SimulationHistoryCreate(BaseModel):
    simulation_type: Literal["buy", "rebalance", "scenario"]
    source: Source
    input: dict[str, Any]
    result: dict[str, Any]
    as_of: datetime | None = None

    @field_validator("input", "result")
    @classmethod
    def _size_limit(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False).encode()) > MAX_JSON_BYTES:
            raise ValueError("저장할 수 있는 크기(256KB)를 넘었습니다.")
        return value


class SimulationHistoryItem(BaseModel):
    id: str
    simulation_type: str
    source: Source
    is_demo: bool
    input: dict[str, Any]
    result: dict[str, Any]
    as_of: datetime | None
    created_at: datetime


class SimulationHistoryResponse(BaseModel):
    items: list[SimulationHistoryItem]


class Limit(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


def decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else Decimal(value)
