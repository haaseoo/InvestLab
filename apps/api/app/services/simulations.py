"""시뮬레이션 계산. 모두 현재 보유 데이터에 가정을 적용한 이론값이며 주문을 실행하지 않는다.

입력 Holding은 apply_weights를 거친 것이어야 한다.
"""

from decimal import ROUND_FLOOR, Decimal

from app.core.errors import HoldingNotFoundError, SimulationInputError
from app.schemas.analysis import (
    THEORETICAL_NOTE,
    BuyRequest,
    PositionState,
    PurchaseDetail,
    RebalanceRequest,
    RebalanceRow,
    ScenarioRequest,
    ScenarioRow,
    StandaloneRow,
    WeightChange,
)
from app.schemas.portfolio import AssetClass, Holding
from app.services.analytics import ASSET_CLASS_LABELS, valued_holdings

HUNDRED = Decimal(100)
ONE = Decimal(1)
WEIGHT_SUM_TOLERANCE = Decimal("0.01")


def holding_key(holding: Holding) -> str:
    return f"{holding.market}:{holding.symbol}"


def _total_value(holdings: list[Holding]) -> Decimal:
    return sum((h.market_value_valuation for h in valued_holdings(holdings)), Decimal(0))


# ---------------------------------------------------------------- 추가 매수


def simulate_buy(holdings: list[Holding], request: BuyRequest, valuation_currency: str) -> dict:
    """계산식

    매수 수량 q = quantity, 또는 amount ÷ price (소수 미허용 시 내림)
    gross = q × price
    총 필요 금액 = gross + 수수료 + 세금 (적용한 항목만)
    새 수량 = 기존 수량 + q
    새 평균단가 = (기존 원금 + gross) ÷ 새 수량  ← 수수료·세금 제외
    새 평가금액(평가 통화) = 새 수량 × 현재가 × 현재 환율

    추가 매수분도 가정 매수가가 아니라 현재가로 평가한다. 다른 종목과 같은 기준으로 비중을
    비교하기 위해서다.
    """
    target = next(
        (h for h in holdings if h.symbol == request.symbol and h.market == request.market), None
    )
    if target is None:
        raise HoldingNotFoundError(details={"symbol": request.symbol, "market": request.market})

    assumptions = [THEORETICAL_NOTE]
    leftover = None
    if request.mode == "quantity":
        quantity = request.quantity
    else:
        raw = request.amount / request.price
        quantity = raw if request.allow_fractional else raw.to_integral_value(ROUND_FLOOR)
        leftover = request.amount - quantity * request.price
        if not request.allow_fractional:
            assumptions.append(
                "금액 모드에서 수량은 1주 단위로 내림하고, 남는 금액은 따로 표시합니다."
            )
    if quantity <= 0:
        raise SimulationInputError("매수 금액이 가정 매수가 1주보다 작습니다.")

    gross = quantity * request.price
    total_cash = gross + (request.fee_amount or 0) + (request.tax_amount or 0)

    if target.currency == valuation_currency:
        fx_used, fx_source = ONE, "same_currency"
    elif request.fx_rate is not None:
        fx_used, fx_source = request.fx_rate, "input"
    elif target.fx_rate is not None:
        fx_used, fx_source = target.fx_rate, "current"
    else:
        fx_used, fx_source = None, "unavailable"

    new_quantity = target.quantity + quantity
    new_cost = target.cost_basis + gross
    new_cost_valuation = (
        target.cost_basis_valuation + gross * fx_used
        if target.cost_basis_valuation is not None and fx_used is not None
        else None
    )
    new_value_valuation = (
        new_quantity * target.current_price * target.fx_rate
        if target.current_price is not None and target.fx_rate is not None
        else None
    )

    total_before = _total_value(holdings)
    if target.market_value_valuation is not None and new_value_valuation is not None:
        total_after = total_before - target.market_value_valuation + new_value_valuation
    else:
        total_after = None

    def after_value(h: Holding) -> Decimal | None:
        return new_value_valuation if h is target else h.market_value_valuation

    weights = [
        WeightChange(
            key=holding_key(h),
            name=h.name,
            before_pct=h.weight_pct,
            after_pct=after_value(h) / total_after * HUNDRED
            if total_after and after_value(h) is not None
            else None,
        )
        for h in valued_holdings(holdings)
    ]

    assumptions += [
        f"추가 매수분도 현재가({target.current_price} {target.currency})로 평가합니다. "
        "가정 매수가는 평균단가와 투자 원금 계산에만 쓰입니다."
        if target.current_price is not None
        else "현재가를 알 수 없어 매수 후 평가금액과 비중을 계산하지 않았습니다.",
        "평균단가와 투자 원금에는 수수료·세금을 포함하지 않습니다. 총 필요 금액에만 포함합니다.",
        "수수료를 적용했습니다."
        if request.fee_amount is not None
        else "수수료는 적용하지 않았습니다.",
        "세금을 적용했습니다." if request.tax_amount is not None else "세금은 적용하지 않았습니다.",
        {
            "same_currency": "거래 통화와 평가 통화가 같아 환율을 적용하지 않습니다.",
            "input": f"원금 환산에 입력한 환율 {request.fx_rate}을 적용했습니다.",
            "current": f"원금 환산에 현재 환율 {target.fx_rate}을 적용했습니다.",
            "unavailable": "환율을 알 수 없어 평가 통화 금액을 계산하지 않았습니다.",
        }[fx_source],
        "예수금 잔고를 확인하지 않습니다. 매수 대금은 별도로 마련한다고 가정합니다.",
    ]

    return {
        "symbol": target.symbol,
        "market": target.market,
        "name": target.name,
        "currency": target.currency,
        "before": PositionState(
            quantity=target.quantity,
            average_cost=target.average_cost,
            cost_basis=target.cost_basis,
            cost_basis_valuation=target.cost_basis_valuation,
            market_value_valuation=target.market_value_valuation,
            weight_pct=target.weight_pct,
        ),
        "after": PositionState(
            quantity=new_quantity,
            average_cost=new_cost / new_quantity,
            cost_basis=new_cost,
            cost_basis_valuation=new_cost_valuation,
            market_value_valuation=new_value_valuation,
            weight_pct=new_value_valuation / total_after * HUNDRED
            if total_after and new_value_valuation is not None
            else None,
        ),
        "purchase": PurchaseDetail(
            quantity=quantity,
            price=request.price,
            gross_amount=gross,
            fee_amount=request.fee_amount,
            tax_amount=request.tax_amount,
            total_cash_required=total_cash,
            total_cash_required_valuation=total_cash * fx_used if fx_used is not None else None,
            fx_rate_used=fx_used,
            fx_rate_source=fx_source,
            leftover_amount=leftover,
        ),
        "total_market_value_before": total_before if valued_holdings(holdings) else None,
        "total_market_value_after": total_after,
        "weights": weights,
        "assumptions": assumptions,
    }


# ---------------------------------------------------------------- 리밸런싱


def _rebalance_groups(holdings: list[Holding], dimension: str) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for h in valued_holdings(holdings):
        if dimension == "holding":
            groups[holding_key(h)] = {"label": h.name, "value": h.market_value_valuation, "h": h}
        else:
            key = h.asset_class.value
            g = groups.setdefault(
                key, {"label": ASSET_CLASS_LABELS[AssetClass(key)], "value": Decimal(0), "h": None}
            )
            g["value"] += h.market_value_valuation
    return groups


def simulate_rebalance(holdings: list[Holding], request: RebalanceRequest) -> dict:
    """계산식 (평가 통화 기준)

    조정 후 총액 T = 현재 평가금액 합 + 추가 현금
    목표 금액 = T × 목표 비중 ÷ 100
    조정 금액 = 목표 금액 − 현재 금액 (양수 매수, 음수 매도)
    이론 수량 = 조정 금액 ÷ (현재가 × 현재 환율) — 종목 단위일 때만, 반올림하지 않음

    목표 비중의 합은 100%(±0.01%p)여야 한다. 요청에 없는 항목은 목표 0%로 보고 표시한다.
    """
    groups = _rebalance_groups(holdings, request.dimension)
    if not groups:
        raise SimulationInputError("평가금액을 아는 종목이 없어 리밸런싱을 계산할 수 없습니다.")

    keys = [t.key for t in request.targets]
    if len(set(keys)) != len(keys):
        raise SimulationInputError("같은 항목의 목표 비중이 두 번 입력되었습니다.")
    unknown = [k for k in keys if k not in groups]
    if unknown:
        raise SimulationInputError(
            "현재 비중을 계산할 수 없는 항목입니다.", details={"unknown_keys": unknown}
        )
    target_sum = sum((t.target_pct for t in request.targets), Decimal(0))
    if abs(target_sum - HUNDRED) > WEIGHT_SUM_TOLERANCE:
        raise SimulationInputError(
            "목표 비중의 합이 100%가 아닙니다.", details={"target_sum": str(target_sum)}
        )

    targets = {t.key: t.target_pct for t in request.targets}
    total_before = sum((g["value"] for g in groups.values()), Decimal(0))
    total_after = total_before + request.additional_cash

    rows = []
    for key, g in sorted(groups.items(), key=lambda item: item[1]["value"], reverse=True):
        target_pct = targets.get(key, Decimal(0))
        current_pct = g["value"] / total_before * HUNDRED
        target_value = total_after * target_pct / HUNDRED
        adjustment = target_value - g["value"]
        h: Holding | None = g["h"]
        unit_value = (
            h.current_price * h.fx_rate
            if h is not None and h.current_price and h.fx_rate is not None
            else None
        )
        rows.append(
            RebalanceRow(
                key=key,
                label=g["label"],
                current_value=g["value"],
                current_pct=current_pct,
                target_pct=target_pct,
                diff_pct=target_pct - current_pct,
                target_value=target_value,
                adjustment_value=adjustment,
                theoretical_quantity=adjustment / unit_value if unit_value else None,
                price_currency=h.currency if h is not None else None,
                implicit_target=key not in targets,
            )
        )

    assumptions = [
        THEORETICAL_NOTE,
        "조정 금액은 현재 평가금액과 현재 환율을 기준으로 계산합니다.",
    ]
    if request.additional_cash > 0:
        assumptions.append("추가 현금을 포함한 총액을 목표 비중대로 나눕니다.")
    if any(r.implicit_target for r in rows):
        assumptions.append("목표를 입력하지 않은 항목은 목표 비중 0%로 계산했습니다.")
    if request.dimension == "holding":
        assumptions.append("이론 수량은 매매 단위로 반올림하지 않은 값입니다.")

    return {
        "dimension": request.dimension,
        "total_before": total_before,
        "additional_cash": request.additional_cash,
        "total_after": total_after,
        "rows": rows,
        "excluded_symbols": [h.symbol for h in holdings if h.market_value_valuation is None],
        "constraints_not_applied": [
            "매매 단위(1주 단위 거래)",
            "수수료와 세금",
            "현금 잔고",
            "주문 시점의 가격 변동",
            "매도 시 실현손익과 과세",
        ],
        "assumptions": assumptions,
    }


# ---------------------------------------------------------------- 하락 시나리오


def simulate_scenario(
    holdings: list[Holding], request: ScenarioRequest, valuation_currency: str
) -> dict:
    """계산식 (평가 통화 기준)

    가격 변화율 p = 종목 지정 변화율, 없으면 자산군 변화율, 둘 다 없으면 0
    환율 변화율 f = 거래 통화에 지정한 변화율, 없으면 0
    변화 후 금액 = 현재 금액 × (1 + p/100) × (1 + f/100)
    전체 영향 비율 = 영향 금액 ÷ 현재 총액 × 100

    종목 지정이 자산군 지정보다 우선하며 둘을 겹쳐 적용하지 않는다.
    standalone: 각 종목만 standalone_change_pct만큼 변할 때의 전체 영향(종목별 민감도).
    """
    valued = valued_holdings(holdings)
    total = _total_value(holdings)
    if total <= 0:
        raise SimulationInputError("평가금액을 아는 종목이 없어 시나리오를 계산할 수 없습니다.")

    holding_keys = {holding_key(h) for h in valued}
    class_keys = {h.asset_class.value for h in valued}
    holding_shocks: dict[str, Decimal] = {}
    class_shocks: dict[str, Decimal] = {}
    for shock in request.shocks:
        known, bucket = (
            (holding_keys, holding_shocks)
            if shock.type == "holding"
            else (class_keys, class_shocks)
        )
        if shock.key not in known:
            raise SimulationInputError(
                "평가금액을 아는 항목이 아닙니다.", details={"key": shock.key}
            )
        if shock.key in bucket:
            raise SimulationInputError("같은 항목의 변화율이 두 번 입력되었습니다.")
        bucket[shock.key] = shock.change_pct

    fx_shocks: dict[str, Decimal] = {}
    for fx in request.fx_shocks:
        if fx.currency == valuation_currency:
            raise SimulationInputError("평가 통화에는 환율 변화를 적용할 수 없습니다.")
        if fx.currency in fx_shocks:
            raise SimulationInputError("같은 통화의 환율 변화율이 두 번 입력되었습니다.")
        fx_shocks[fx.currency] = fx.change_pct

    rows = []
    for h in valued:
        key = holding_key(h)
        if key in holding_shocks:
            p, p_source = holding_shocks[key], "holding"
        elif h.asset_class.value in class_shocks:
            p, p_source = class_shocks[h.asset_class.value], "asset_class"
        else:
            p, p_source = Decimal(0), "none"
        f = fx_shocks.get(h.currency, Decimal(0))
        before = h.market_value_valuation
        after = before * (ONE + p / HUNDRED) * (ONE + f / HUNDRED)
        rows.append(
            ScenarioRow(
                key=key,
                symbol=h.symbol,
                name=h.name,
                asset_class=h.asset_class.value,
                value_before=before,
                price_change_pct=p,
                price_change_source=p_source,
                fx_change_pct=f,
                value_after=after,
                impact=after - before,
                impact_on_total_pct=(after - before) / total * HUNDRED,
            )
        )
    total_after = sum((r.value_after for r in rows), Decimal(0))

    standalone = []
    if request.standalone_change_pct is not None:
        s = request.standalone_change_pct
        standalone = sorted(
            (
                StandaloneRow(
                    key=holding_key(h),
                    symbol=h.symbol,
                    name=h.name,
                    weight_pct=h.weight_pct,
                    impact=h.market_value_valuation * s / HUNDRED,
                    impact_on_total_pct=h.market_value_valuation * s / total,
                )
                for h in valued
            ),
            key=lambda r: abs(r.impact),
            reverse=True,
        )

    return {
        "total_before": total,
        "total_after": total_after,
        "total_change": total_after - total,
        "total_change_pct": (total_after - total) / total * HUNDRED,
        "rows": sorted(rows, key=lambda r: r.impact),
        "standalone_change_pct": request.standalone_change_pct,
        "standalone": standalone,
        "excluded_symbols": [h.symbol for h in holdings if h.market_value_valuation is None],
        "assumptions": [
            "가정한 변화율을 적용한 민감도 분석이며 예측이 아닙니다.",
            "종목에 지정한 변화율이 자산군 변화율보다 우선하며 둘을 겹쳐 적용하지 않습니다.",
            "환율 변화는 거래 통화가 해당 통화인 종목에만 적용합니다. 원화로 거래되는 해외 ETF의 "
            "환 노출은 반영하지 않습니다.",
            "종목 간 상관관계와 연쇄 효과는 반영하지 않습니다.",
        ],
    }
