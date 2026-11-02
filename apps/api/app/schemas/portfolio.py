"""공통 금융 데이터 모델.

- 내부 계산은 반올림하지 않은 Decimal로 수행하고, JSON 직렬화 시점에만 자릿수를 맞춘다.
- JSON에서 Decimal은 문자열이다(부동소수점 오차 방지).
- 값을 알 수 없으면 None(null)이다. 0은 실제 0을 뜻한다.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _fixed(places: str):
    return lambda value: format(Decimal(value).quantize(Decimal(places), ROUND_HALF_UP), "f")


# 입력값 그대로(수량, 단가, 환율): 자릿수를 임의로 줄이지 않는다.
Exact = Annotated[
    Decimal, PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json")
]
# 계산된 금액: 소수 둘째 자리
Money = Annotated[Decimal, PlainSerializer(_fixed("0.01"), return_type=str, when_used="json")]
# 계산된 비율(%): 소수 넷째 자리
Percent = Annotated[Decimal, PlainSerializer(_fixed("0.0001"), return_type=str, when_used="json")]

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class Source(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class AssetType(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    OTHER = "other"


class AssetClass(StrEnum):
    BROAD_INDEX_ETF = "broad_index_etf"
    SECTOR_ETF = "sector_etf"
    DOMESTIC_STOCK = "domestic_stock"
    OVERSEAS_STOCK = "overseas_stock"
    OTHER = "other"


class ValuationStatus(StrEnum):
    REPORTED = "reported"  # Provider가 평가금액을 직접 제공
    CALCULATED = "calculated"  # 조회한 현재가 × 수량으로 계산
    UNAVAILABLE = "unavailable"  # 시세 조회 실패 또는 시세 없음


class Position(BaseModel):
    """Provider가 시세와 무관하게 알고 있는 보유 정보."""

    symbol: str
    market: str
    asset_type: AssetType
    asset_class: AssetClass
    name: str
    quantity: Decimal = Field(ge=0)
    average_cost: Decimal = Field(ge=0)
    currency: CurrencyCode
    country: str | None = None
    sector: str | None = None


class Quote(BaseModel):
    symbol: str
    market: str
    price: Exact | None
    currency: CurrencyCode
    as_of: datetime | None
    source: Source
    is_demo: bool


class FxRate(BaseModel):
    base_currency: CurrencyCode
    quote_currency: CurrencyCode
    rate: Exact = Field(gt=0)
    as_of: datetime
    source: Source


class Holding(BaseModel):
    symbol: str
    market: str
    asset_type: AssetType
    asset_class: AssetClass
    name: str
    country: str | None
    sector: str | None

    quantity: Exact
    average_cost: Exact
    current_price: Exact | None

    # 거래 통화 기준
    currency: CurrencyCode
    cost_basis: Money
    market_value: Money | None
    unrealized_pnl: Money | None
    unrealized_pnl_pct: Percent | None

    # 평가 통화 기준. 환율이 없으면 None이며 합계에서 제외된다.
    valuation_currency: CurrencyCode
    fx_rate: Exact | None
    fx_as_of: datetime | None
    cost_basis_valuation: Money | None
    market_value_valuation: Money | None
    unrealized_pnl_valuation: Money | None
    weight_pct: Percent | None = None

    valuation_status: ValuationStatus
    as_of: datetime | None
    source: Source
    is_demo: bool


class PortfolioSummary(BaseModel):
    valuation_currency: CurrencyCode
    total_cost_basis: Money | None
    total_market_value: Money | None
    # 평가금액을 아는 종목의 원금. 손익·수익률의 분모이며 total_cost_basis와 다를 수 있다.
    valued_cost_basis: Money | None
    total_unrealized_pnl: Money | None
    total_unrealized_pnl_pct: Percent | None
    holding_count: int
    valued_holding_count: int
    unvalued_symbols: list[str]
    is_complete: bool


class AllocationSlice(BaseModel):
    key: str
    label: str
    market_value: Money
    weight_pct: Percent
    holding_count: int


class Concentration(BaseModel):
    """상위 N개 종목의 평가 비중 합. 평가 가능한 종목이 없으면 모두 None."""

    top1_pct: Percent | None
    top3_pct: Percent | None
    top5_pct: Percent | None


class AccountSummary(BaseModel):
    account_masked: str | None
    # None은 "예수금 정보 없음"이다. 0으로 해석하지 않는다.
    cash_balances: dict[str, Exact] | None
    as_of: datetime | None
    source: Source
    is_demo: bool


class SnapshotPoint(BaseModel):
    captured_at: datetime
    total_market_value: Money
    total_cost_basis: Money
    valuation_currency: CurrencyCode


class ProviderCheck(BaseModel):
    key: str
    label: str
    ok: bool


class ProviderStatus(BaseModel):
    source: Source
    state: str  # ready | not_configured | not_implemented
    is_demo: bool
    label: str
    message: str
    checks: list[ProviderCheck] = []


class ResponseMeta(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    source: Source
    is_demo: bool
    as_of: datetime | None
    retrieved_at: datetime
    valuation_currency: CurrencyCode


class HoldingsResponse(ResponseMeta):
    holdings: list[Holding]


class SummaryResponse(ResponseMeta):
    summary: PortfolioSummary
    concentration: Concentration
    assumptions: list[str]


class AllocationResponse(ResponseMeta):
    dimension: str
    slices: list[AllocationSlice]
    # 평가금액을 알 수 없어 비중에서 제외된 종목
    excluded_symbols: list[str]


class PortfolioResponse(SummaryResponse):
    fx_rates: list[FxRate]
    holdings: list[Holding]
    allocation: list[AllocationSlice]


class HistoryResponse(BaseModel):
    source: Source
    is_demo: bool
    retrieved_at: datetime
    points: list[SnapshotPoint]


class ProvidersStatusResponse(BaseModel):
    default_source: Source
    providers: list[ProviderStatus]
