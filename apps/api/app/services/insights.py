"""분석 엔진 인사이트. 계산된 수치를 문장으로 옮길 뿐 판단·권유·예측을 하지 않는다.

AI가 아니다. "높다/위험하다" 같은 임계값 판단을 넣지 않고, 데이터가 없는 항목은 없다고 쓴다.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.schemas.analysis import Insight, OverlapAnalysis
from app.schemas.portfolio import AllocationSlice, Concentration, Holding


def pct(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), ROUND_HALF_UP)}%"


def _largest(slices: list[AllocationSlice]) -> AllocationSlice | None:
    classified = [s for s in slices if not s.is_unclassified]
    return classified[0] if classified else None


def _unclassified(slices: list[AllocationSlice]) -> AllocationSlice | None:
    return next((s for s in slices if s.is_unclassified), None)


def build_insights(
    holdings: list[Holding],
    concentration: Concentration,
    allocations: dict[str, list[AllocationSlice]],
    overlap: OverlapAnalysis,
    valuation_currency: str,
) -> list[Insight]:
    """apply_weights를 거친 Holding을 받는다. 순서는 집중도 → 자산군 → 지역 → 중복 → 섹터 →
    통화 → 손실 종목 → 데이터 한계다."""
    insights: list[Insight] = []
    ranked = sorted(
        (h for h in holdings if h.weight_pct is not None),
        key=lambda h: h.weight_pct,
        reverse=True,
    )

    if concentration.top3_pct is not None:
        names = ", ".join(h.name for h in ranked[:3])
        insights.append(
            Insight(
                key="top3",
                title=f"상위 3개 종목 비중 {pct(concentration.top3_pct)}",
                detail=f"{names}. 보유 종목 단위로 계산했습니다.",
            )
        )

    if largest := _largest(allocations.get("asset_class", [])):
        insights.append(
            Insight(
                key="asset_class",
                title=f"{largest.label} 비중 {pct(largest.weight_pct)}",
                detail=f"자산군 {len(allocations['asset_class'])}개 중 가장 큰 비중입니다.",
            )
        )

    countries = allocations.get("exposure_country", [])
    if largest := _largest(countries):
        detail = "국내 상장 해외지수 ETF는 추종 지수의 국가로 분류했습니다."
        if unclassified := _unclassified(countries):
            detail += f" 국가로 나눌 수 없는 자산 {pct(unclassified.weight_pct)}는 따로 표시합니다."
        insights.append(
            Insight(
                key="exposure_country",
                title=f"투자 대상 국가 중 {largest.label} {pct(largest.weight_pct)}",
                detail=detail,
            )
        )

    for group in overlap.benchmark_groups:
        names = ", ".join(h.name for h in group.holdings)
        insights.append(
            Insight(
                key=f"benchmark:{group.benchmark}",
                title=f"{group.benchmark} 추종 ETF {len(group.holdings)}개 · 합계 "
                f"{pct(group.combined_weight_pct)}",
                detail=f"{names}. 같은 지수를 추종하는 상품을 함께 보유하고 있습니다.",
            )
        )

    sectors = allocations.get("sector", [])
    if largest := _largest(sectors):
        detail = f"{', '.join(largest.symbols)}."
        if unclassified := _unclassified(sectors):
            detail += (
                f" 섹터 정보가 없는 자산 {pct(unclassified.weight_pct)}(지수 ETF 등)의 내부 섹터 "
                "노출은 포함하지 않았습니다."
            )
        insights.append(
            Insight(
                key="sector",
                title=f"섹터 '{largest.label}' 비중 {pct(largest.weight_pct)}",
                detail=detail,
            )
        )

    foreign = [s for s in allocations.get("currency", []) if s.key != valuation_currency]
    for slice_ in foreign:
        insights.append(
            Insight(
                key=f"currency:{slice_.key}",
                title=f"{slice_.key} 거래 자산 {pct(slice_.weight_pct)}",
                detail="거래 통화 기준입니다. 원화로 거래되는 해외 ETF의 환 노출은 포함하지 않았습니다.",
            )
        )

    losers = [h for h in ranked if h.unrealized_pnl_pct is not None and h.unrealized_pnl_pct < 0]
    if losers:
        listed = ", ".join(f"{h.name} {pct(h.unrealized_pnl_pct)}" for h in losers)
        insights.append(
            Insight(
                key="losers",
                title=f"평가손실 종목 {len(losers)}개",
                detail=f"{listed}. 평가손익 기준입니다.",
            )
        )

    constituent = overlap.constituent_overlap
    if constituent.status == "unavailable":
        insights.append(
            Insight(
                key="etf_data",
                title="ETF 구성 종목 중복은 계산하지 않았습니다",
                detail=f"보유 ETF {len(constituent.missing_etfs)}개의 구성 종목 데이터가 없습니다.",
            )
        )
    elif constituent.status == "partial":
        insights.append(
            Insight(
                key="etf_data",
                title="ETF 구성 종목 중복은 일부만 계산했습니다",
                detail=f"구성 종목 데이터 없음: {', '.join(constituent.missing_etfs)}",
            )
        )

    return insights
