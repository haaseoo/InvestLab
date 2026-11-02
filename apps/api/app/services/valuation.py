"""보유 종목 1건의 평가. 모든 Provider가 이 함수를 거쳐 동일한 Holding을 만든다."""

from decimal import Decimal

from app.schemas.portfolio import (
    FxRate,
    Holding,
    Position,
    Quote,
    Source,
    ValuationStatus,
)

HUNDRED = Decimal(100)


def find_fx_rate(currency: str, valuation_currency: str, fx_rates: list[FxRate]) -> FxRate | None:
    """직접 환율만 사용한다. 역수·교차 환율을 추정해 만들지 않는다."""
    for fx in fx_rates:
        if fx.base_currency == currency and fx.quote_currency == valuation_currency:
            return fx
    return None


def build_holding(
    position: Position,
    quote: Quote | None,
    fx_rates: list[FxRate],
    valuation_currency: str,
    source: Source,
    is_demo: bool,
    reported_market_value: Decimal | None = None,
) -> Holding:
    """계산식

    cost_basis = quantity × average_cost
    market_value = reported_market_value 또는 quantity × current_price
    unrealized_pnl = market_value − cost_basis
    unrealized_pnl_pct = unrealized_pnl ÷ cost_basis × 100 (원금이 0이면 None)
    *_valuation = 거래 통화 금액 × fx_rate (같은 통화면 fx_rate = 1)

    전제: 환산에는 현재 환율 하나를 쓴다. 매입 시점 환율을 모르므로 환차손익은 반영되지 않는다.
    """
    if quote is not None and quote.currency != position.currency:
        raise ValueError(
            f"{position.symbol}: 시세 통화({quote.currency})와 보유 통화({position.currency})가 다릅니다."
        )

    price = quote.price if quote else None
    cost_basis = position.quantity * position.average_cost

    if reported_market_value is not None:
        market_value, status = reported_market_value, ValuationStatus.REPORTED
    elif price is not None:
        market_value, status = position.quantity * price, ValuationStatus.CALCULATED
    else:
        market_value, status = None, ValuationStatus.UNAVAILABLE

    pnl = market_value - cost_basis if market_value is not None else None
    pnl_pct = pnl / cost_basis * HUNDRED if pnl is not None and cost_basis > 0 else None

    if position.currency == valuation_currency:
        fx_rate, fx_as_of = Decimal(1), None
    else:
        fx = find_fx_rate(position.currency, valuation_currency, fx_rates)
        fx_rate, fx_as_of = (fx.rate, fx.as_of) if fx else (None, None)

    def convert(amount: Decimal | None) -> Decimal | None:
        return amount * fx_rate if amount is not None and fx_rate is not None else None

    return Holding(
        symbol=position.symbol,
        market=position.market,
        asset_type=position.asset_type,
        asset_class=position.asset_class,
        name=position.name,
        country=position.country,
        exposure_country=position.exposure_country,
        sector=position.sector,
        benchmark=position.benchmark,
        quantity=position.quantity,
        average_cost=position.average_cost,
        current_price=price,
        currency=position.currency,
        cost_basis=cost_basis,
        market_value=market_value,
        unrealized_pnl=pnl,
        unrealized_pnl_pct=pnl_pct,
        valuation_currency=valuation_currency,
        fx_rate=fx_rate,
        fx_as_of=fx_as_of,
        cost_basis_valuation=convert(cost_basis),
        market_value_valuation=convert(market_value),
        unrealized_pnl_valuation=convert(pnl),
        valuation_status=status,
        as_of=quote.as_of if quote else None,
        source=source,
        is_demo=is_demo,
    )
