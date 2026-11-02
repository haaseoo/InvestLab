"""포트폴리오 집계 계산. AI와 분리된 순수 함수이며, 입력은 평가 통화로 환산된 Holding이다.

수익률은 평가손익 기준이다. 배당·분배금, 수수료, 세금, 입출금, 실현손익은 포함하지 않으므로
총수익률(total return)과 다르다.
"""

from collections.abc import Callable
from decimal import Decimal

from app.schemas.portfolio import (
    AllocationSlice,
    AssetClass,
    AssetType,
    Concentration,
    Holding,
    PortfolioSummary,
)

HUNDRED = Decimal(100)
TEN_THOUSAND = Decimal(10000)
UNCLASSIFIED_KEY = "unclassified"

ASSET_CLASS_LABELS = {
    AssetClass.BROAD_INDEX_ETF: "시장지수 ETF",
    AssetClass.SECTOR_ETF: "섹터·테마 ETF",
    AssetClass.DOMESTIC_STOCK: "국내 개별주",
    AssetClass.OVERSEAS_STOCK: "해외 개별주",
    AssetClass.ETF_UNCLASSIFIED: "ETF (유형 미분류)",
    AssetClass.OTHER: "기타 자산",
}
ASSET_TYPE_LABELS = {
    AssetType.STOCK: "주식",
    AssetType.ETF: "ETF",
    AssetType.OTHER: "기타",
}
COUNTRY_LABELS = {"KR": "한국", "US": "미국", "JP": "일본", "CN": "중국", "HK": "홍콩"}

UNCLASSIFIED_LABELS = {
    "exposure_country": "국가 구분 없음",
    "sector": "섹터 정보 없음",
}

KeyFn = Callable[[Holding], str | None]
LabelFn = Callable[[str], str]

ALLOCATION_DIMENSIONS: dict[str, tuple[KeyFn, LabelFn]] = {
    "asset_class": (lambda h: h.asset_class.value, lambda k: ASSET_CLASS_LABELS[AssetClass(k)]),
    "asset_type": (lambda h: h.asset_type.value, lambda k: ASSET_TYPE_LABELS[AssetType(k)]),
    "market": (lambda h: h.market, lambda k: k),
    "currency": (lambda h: h.currency, lambda k: k),
    "exposure_country": (lambda h: h.exposure_country, lambda k: COUNTRY_LABELS.get(k, k)),
    "sector": (lambda h: h.sector, lambda k: k),
}

ASSUMPTIONS = [
    "수익률은 평가손익 기준이며 배당·분배금, 수수료, 세금, 입출금, 실현손익을 반영하지 않습니다.",
    "외화 자산은 기준 시점의 환율 하나로 환산합니다. 매입 시점 환율을 알 수 없어 환차손익은 "
    "반영되지 않습니다.",
    "평가자산에 예수금(현금)은 포함하지 않습니다.",
]


def _require_single_valuation_currency(holdings: list[Holding]) -> None:
    currencies = {h.valuation_currency for h in holdings}
    if len(currencies) > 1:
        raise ValueError(f"평가 통화가 섞여 있어 합산할 수 없습니다: {sorted(currencies)}")


def _sum_or_none(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) if values else None


def valued_holdings(holdings: list[Holding]) -> list[Holding]:
    """평가 통화 금액을 아는 종목. 비중 계산의 대상이다."""
    return [h for h in holdings if h.market_value_valuation is not None]


def compute_summary(holdings: list[Holding], valuation_currency: str) -> PortfolioSummary:
    """total_cost_basis = Σ 환산 원금
    total_market_value = Σ 환산 평가금액
    total_unrealized_pnl = Σ 환산 평가손익 (평가금액을 아는 종목만)
    total_unrealized_pnl_pct = total_unrealized_pnl ÷ valued_cost_basis × 100

    시세나 환율이 없는 종목은 합계에서 빠지고 unvalued_symbols에 기록된다. 값이 하나도 없으면
    합계는 0이 아니라 None이다.
    """
    _require_single_valuation_currency(holdings)
    valued = valued_holdings(holdings)

    total_cost = _sum_or_none(
        [h.cost_basis_valuation for h in holdings if h.cost_basis_valuation is not None]
    )
    total_value = _sum_or_none([h.market_value_valuation for h in valued])
    valued_cost = _sum_or_none([h.cost_basis_valuation for h in valued])
    total_pnl = _sum_or_none([h.unrealized_pnl_valuation for h in valued])
    pnl_pct = total_pnl / valued_cost * HUNDRED if total_pnl is not None and valued_cost else None
    unvalued = [h.symbol for h in holdings if h.market_value_valuation is None]

    return PortfolioSummary(
        valuation_currency=valuation_currency,
        total_cost_basis=total_cost,
        total_market_value=total_value,
        valued_cost_basis=valued_cost,
        total_unrealized_pnl=total_pnl,
        total_unrealized_pnl_pct=pnl_pct,
        holding_count=len(holdings),
        valued_holding_count=len(valued),
        unvalued_symbols=unvalued,
        is_complete=not unvalued,
    )


def apply_weights(holdings: list[Holding]) -> list[Holding]:
    """weight_pct = 종목 환산 평가금액 ÷ 평가 가능한 종목의 환산 평가금액 합 × 100"""
    _require_single_valuation_currency(holdings)
    total = sum((h.market_value_valuation for h in valued_holdings(holdings)), Decimal(0))
    return [
        h.model_copy(
            update={
                "weight_pct": h.market_value_valuation / total * HUNDRED
                if h.market_value_valuation is not None and total > 0
                else None
            }
        )
        for h in holdings
    ]


def compute_allocation(holdings: list[Holding], dimension: str) -> list[AllocationSlice]:
    """차원별 평가금액 합과 비중.

    - 평가금액을 알 수 없는 종목은 제외한다.
    - 분류 값이 없는 종목(예: 지수 ETF의 섹터)은 추정하지 않고 "정보 없음" 묶음으로 모은다.
      이 묶음은 is_unclassified=True이며 항상 마지막에 둔다.
    - 나머지는 비중이 큰 순으로 정렬한다.
    """
    _require_single_valuation_currency(holdings)
    key_of, label_of = ALLOCATION_DIMENSIONS[dimension]
    valued = valued_holdings(holdings)
    total = sum((h.market_value_valuation for h in valued), Decimal(0))
    if total <= 0:
        return []

    groups: dict[str | None, list[Holding]] = {}
    for holding in valued:
        groups.setdefault(key_of(holding), []).append(holding)

    slices = []
    for key, members in groups.items():
        value = sum((h.market_value_valuation for h in members), Decimal(0))
        slices.append(
            AllocationSlice(
                key=key if key is not None else UNCLASSIFIED_KEY,
                label=label_of(key)
                if key is not None
                else UNCLASSIFIED_LABELS.get(dimension, "분류 정보 없음"),
                market_value=value,
                weight_pct=value / total * HUNDRED,
                holding_count=len(members),
                is_unclassified=key is None,
                symbols=[h.symbol for h in members],
            )
        )
    return sorted(slices, key=lambda s: (s.is_unclassified, -s.market_value))


def compute_concentration(holdings: list[Holding]) -> Concentration:
    """apply_weights를 거친 Holding을 받는다.

    topN_pct = 비중 상위 N개 종목의 weight_pct 합. 종목 수가 N보다 적으면 있는 종목만 합산한다.
    hhi = Σ weight_pct². 한 종목에 100%면 10000, n개에 똑같이 나누면 10000/n이다.
    effective_holdings = 10000 ÷ hhi.

    보유 종목 단위의 계산이다. ETF 내부 편입 종목은 펼치지 않는다.
    """
    weights = sorted((h.weight_pct for h in holdings if h.weight_pct is not None), reverse=True)
    if not weights:
        return Concentration(top1_pct=None, top3_pct=None, top5_pct=None)
    hhi = sum((w * w for w in weights), Decimal(0))
    return Concentration(
        top1_pct=weights[0],
        top3_pct=sum(weights[:3], Decimal(0)),
        top5_pct=sum(weights[:5], Decimal(0)),
        hhi=hhi,
        effective_holdings=TEN_THOUSAND / hhi if hhi > 0 else None,
    )
