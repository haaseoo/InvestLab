"""포트폴리오 스냅샷 생성과 검증.

저장 조건(하나라도 어기면 저장하지 않는다)
- 실제 데이터만: Provider가 Mock(is_demo)이거나 source가 live가 아니면 거부한다.
- 기준 시각(as_of)이 있어야 한다.
- 평가 통화가 하나여야 하고, 총 평가금액·총 원금을 알아야 한다.
- 총액은 종목 금액의 합과 정확히 같아야 한다. 저장 정밀도(소수 4자리)로 맞춘 뒤 합산하므로
  DB에 들어간 값끼리 항상 일치한다.
- 평가금액이 없는 종목은 valuation_status가 unavailable이어야 한다.
"""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import MockSnapshotForbiddenError, SnapshotIntegrityError
from app.providers.base import PortfolioProvider
from app.schemas.portfolio import Holding, Source, ValuationStatus
from app.schemas.user_data import SnapshotHolding, SnapshotRecord
from app.services.analytics import apply_weights, compute_summary

STORE = Decimal("0.0001")


def _q(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(STORE, ROUND_HALF_UP)


def _holding_row(h: Holding) -> SnapshotHolding:
    if (h.market_value is None) != (h.valuation_status is ValuationStatus.UNAVAILABLE):
        raise SnapshotIntegrityError(details={"symbol": h.symbol, "reason": "평가 상태 불일치"})
    return SnapshotHolding(
        symbol=h.symbol,
        market=h.market,
        name=h.name,
        asset_type=h.asset_type.value,
        quantity=h.quantity,
        average_cost=h.average_cost,
        current_price=h.current_price,
        currency=h.currency,
        cost_basis=_q(h.cost_basis),
        market_value=_q(h.market_value),
        fx_rate=h.fx_rate,
        cost_basis_valuation=_q(h.cost_basis_valuation),
        market_value_valuation=_q(h.market_value_valuation),
        valuation_status=h.valuation_status.value,
    )


def build_snapshot_record(
    provider: PortfolioProvider, holdings: list[Holding], fx_rates, valuation_currency: str
) -> SnapshotRecord:
    if provider.is_demo or provider.source is not Source.LIVE:
        raise MockSnapshotForbiddenError()
    if any(h.is_demo or h.source is not Source.LIVE for h in holdings):
        raise MockSnapshotForbiddenError()

    holdings = apply_weights(holdings)
    summary = compute_summary(holdings, valuation_currency)
    if summary.total_market_value is None or summary.total_cost_basis is None:
        raise SnapshotIntegrityError("평가금액이나 원금을 알 수 없어 저장하지 않았습니다.")

    timestamps = [h.as_of for h in holdings if h.as_of is not None]
    if not timestamps:
        raise SnapshotIntegrityError("기준 시각이 없는 데이터는 저장하지 않습니다.")
    as_of = min(timestamps)

    rows = [_holding_row(h) for h in holdings]
    total_value = sum(
        (r.market_value_valuation for r in rows if r.market_value_valuation is not None), Decimal(0)
    )
    total_cost = sum(
        (r.cost_basis_valuation for r in rows if r.cost_basis_valuation is not None), Decimal(0)
    )
    # 반올림 전 합계와 저장 합계의 차이는 종목당 최대 0.00005다. 그보다 크면 계산 오류다.
    tolerance = STORE * len(rows)
    if (
        abs(total_value - summary.total_market_value) > tolerance
        or abs(total_cost - summary.total_cost_basis) > tolerance
    ):
        raise SnapshotIntegrityError("종목 합계와 총액이 일치하지 않습니다.")

    payload = {
        "as_of": as_of.isoformat(),
        "valuation_currency": valuation_currency,
        "holdings": [r.model_dump(mode="json") for r in rows],
        "fx_rates": [fx.model_dump(mode="json") for fx in fx_rates],
    }
    content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    return SnapshotRecord(
        source=Source.LIVE,
        valuation_currency=valuation_currency,
        total_market_value=total_value,
        total_cost_basis=total_cost,
        holding_count=summary.holding_count,
        valued_holding_count=summary.valued_holding_count,
        is_complete=summary.is_complete,
        fx_rates=fx_rates,
        as_of=as_of,
        content_hash=content_hash,
        holdings=rows,
    )


async def capture(provider: PortfolioProvider, valuation_currency: str) -> SnapshotRecord:
    if provider.is_demo:
        raise MockSnapshotForbiddenError()
    holdings = await provider.get_holdings(valuation_currency)
    fx_rates = await provider.get_fx_rates()
    return build_snapshot_record(provider, holdings, fx_rates, valuation_currency)
