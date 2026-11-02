"""분석·시뮬레이션 응답 모델. 금액은 Decimal이며 JSON에서는 문자열이다."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.portfolio import (
    AllocationSlice,
    Concentration,
    CurrencyCode,
    Exact,
    Money,
    Percent,
    ResponseMeta,
)

# ---------------------------------------------------------------- ETF 중복


class EtfConstituent(BaseModel):
    symbol: str
    market: str | None = None
    name: str
    weight_pct: Decimal = Field(ge=0, le=100)


class EtfComposition(BaseModel):
    """ETF 구성 종목 스냅샷. 실제 제공처의 데이터만 담는다."""

    etf_symbol: str
    etf_market: str
    as_of: datetime
    provider: str  # 데이터 제공처 이름
    constituents: list[EtfConstituent]

    @model_validator(mode="after")
    def _weights_not_over_100(self):
        total = sum((c.weight_pct for c in self.constituents), Decimal(0))
        # 제공처 반올림을 감안해 0.5%p까지 허용한다.
        if total > Decimal("100.5"):
            raise ValueError(f"{self.etf_symbol}: 구성 비중 합이 100%를 넘습니다 ({total})")
        return self


class HoldingRef(BaseModel):
    symbol: str
    market: str
    name: str
    weight_pct: Percent


class BenchmarkGroup(BaseModel):
    """같은 지수를 추종하는 ETF 묶음. 메타데이터(추종 지수)만으로 판단한다."""

    benchmark: str
    holdings: list[HoldingRef]
    combined_weight_pct: Percent


class ExposurePath(BaseModel):
    via: str  # "direct" 또는 ETF 종목코드
    market_value: Money


class LookThroughExposure(BaseModel):
    symbol: str
    market: str | None
    name: str
    total_value: Money
    weight_pct: Percent
    paths: list[ExposurePath]


class ConstituentOverlap(BaseModel):
    """ETF 구성 종목을 펼쳐 계산한 실제 중복 노출.

    status
    - not_applicable: 보유 ETF가 없음
    - unavailable: 보유 ETF의 구성 종목 데이터가 하나도 없음
    - partial: 일부 ETF만 데이터가 있음. 결과는 데이터가 있는 ETF만 반영
    - complete: 모든 보유 ETF의 데이터가 있음
    """

    status: Literal["not_applicable", "unavailable", "partial", "complete"]
    covered_etfs: list[str]
    missing_etfs: list[str]
    overlaps: list[LookThroughExposure]


class OverlapAnalysis(BaseModel):
    benchmark_groups: list[BenchmarkGroup]
    constituent_overlap: ConstituentOverlap


# ---------------------------------------------------------------- 위험·인사이트


class UnavailableMetric(BaseModel):
    key: str
    label: str
    reason: str


class Insight(BaseModel):
    """분석 엔진이 계산한 사실. 판단·권유·예측을 담지 않는다."""

    key: str
    title: str
    detail: str


class RiskResponse(ResponseMeta):
    concentration: Concentration
    allocations: dict[str, list[AllocationSlice]]
    overlap: OverlapAnalysis
    unavailable_metrics: list[UnavailableMetric]
    insights: list[Insight]
    excluded_symbols: list[str]
    assumptions: list[str]


# ---------------------------------------------------------------- 시뮬레이션 공통

THEORETICAL_NOTE = "이론적 시뮬레이션입니다. 실제 주문이 아니며 미래 결과를 예측하지 않습니다."

ChangePct = Decimal  # 퍼센트 단위 변화율. -20은 20% 하락


class SimulationMeta(ResponseMeta):
    is_theoretical: bool = True
    assumptions: list[str]


class WeightChange(BaseModel):
    key: str
    name: str
    before_pct: Percent | None
    after_pct: Percent | None


# ---------------------------------------------------------------- 추가 매수


class BuyRequest(BaseModel):
    symbol: str
    market: str
    mode: Literal["quantity", "amount"]
    quantity: Decimal | None = Field(default=None, gt=0)
    # 거래 통화 기준 매수 예정 금액(수수료·세금 제외)
    amount: Decimal | None = Field(default=None, gt=0)
    price: Decimal = Field(gt=0, description="가정 매수가, 거래 통화")
    allow_fractional: bool = False
    # None이면 미적용. 거래 통화 기준
    fee_amount: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)
    # None이면 현재 환율 사용. 거래 통화 = 평가 통화면 무시
    fx_rate: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _mode_fields(self):
        if self.mode == "quantity" and self.quantity is None:
            raise ValueError("quantity 모드에는 quantity가 필요합니다.")
        if self.mode == "amount" and self.amount is None:
            raise ValueError("amount 모드에는 amount가 필요합니다.")
        if self.mode == "quantity" and not self.allow_fractional and self.quantity % 1 != 0:
            raise ValueError("소수점 수량은 allow_fractional=true일 때만 허용됩니다.")
        return self


class PositionState(BaseModel):
    quantity: Exact
    average_cost: Money
    cost_basis: Money
    cost_basis_valuation: Money | None
    market_value_valuation: Money | None
    weight_pct: Percent | None


class PurchaseDetail(BaseModel):
    quantity: Exact
    price: Exact
    gross_amount: Money
    fee_amount: Money | None
    tax_amount: Money | None
    total_cash_required: Money
    total_cash_required_valuation: Money | None
    fx_rate_used: Exact | None
    fx_rate_source: Literal["same_currency", "input", "current", "unavailable"]
    # 금액 모드에서 수량을 내림하고 남은 금액(거래 통화)
    leftover_amount: Money | None


class BuyResponse(SimulationMeta):
    symbol: str
    market: str
    name: str
    currency: CurrencyCode
    before: PositionState
    after: PositionState
    purchase: PurchaseDetail
    total_market_value_before: Money | None
    total_market_value_after: Money | None
    weights: list[WeightChange]


# ---------------------------------------------------------------- 리밸런싱


class TargetWeight(BaseModel):
    key: str
    target_pct: Decimal = Field(ge=0, le=100)


class RebalanceRequest(BaseModel):
    dimension: Literal["holding", "asset_class"]
    targets: list[TargetWeight] = Field(min_length=1)
    # 새로 넣을 현금(평가 통화). 0이면 현재 평가금액 안에서만 조정
    additional_cash: Decimal = Field(default=Decimal(0), ge=0)


class RebalanceRow(BaseModel):
    key: str
    label: str
    current_value: Money
    current_pct: Percent
    target_pct: Percent
    diff_pct: Percent
    target_value: Money
    adjustment_value: Money
    # 종목 단위일 때만. 조정 금액 ÷ (현재가 × 환율), 매매 단위로 반올림하지 않은 이론값
    theoretical_quantity: Exact | None
    price_currency: CurrencyCode | None
    implicit_target: bool  # 요청에 없어서 목표 0%로 본 항목


class RebalanceResponse(SimulationMeta):
    dimension: str
    total_before: Money
    additional_cash: Money
    total_after: Money
    rows: list[RebalanceRow]
    excluded_symbols: list[str]
    constraints_not_applied: list[str]


# ---------------------------------------------------------------- 하락 시나리오


class Shock(BaseModel):
    type: Literal["holding", "asset_class"]
    key: str
    change_pct: Decimal = Field(ge=-100, le=1000)


class FxShock(BaseModel):
    currency: CurrencyCode
    change_pct: Decimal = Field(ge=-100, le=1000)


class ScenarioRequest(BaseModel):
    shocks: list[Shock] = []
    fx_shocks: list[FxShock] = []
    # 설정하면 종목마다 "그 종목만 이만큼 변할 때"의 전체 영향을 따로 계산한다.
    standalone_change_pct: Decimal | None = Field(default=None, ge=-100, le=1000)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.shocks and not self.fx_shocks and self.standalone_change_pct is None:
            raise ValueError("가정 변화율을 하나 이상 입력해야 합니다.")
        return self


class ScenarioRow(BaseModel):
    key: str
    symbol: str
    name: str
    asset_class: str
    value_before: Money
    price_change_pct: Percent
    price_change_source: Literal["holding", "asset_class", "none"]
    fx_change_pct: Percent
    value_after: Money
    impact: Money
    impact_on_total_pct: Percent


class StandaloneRow(BaseModel):
    key: str
    symbol: str
    name: str
    weight_pct: Percent
    impact: Money
    impact_on_total_pct: Percent


class ScenarioResponse(SimulationMeta):
    total_before: Money
    total_after: Money
    total_change: Money
    total_change_pct: Percent
    rows: list[ScenarioRow]
    standalone_change_pct: Percent | None
    standalone: list[StandaloneRow]
    excluded_symbols: list[str]
