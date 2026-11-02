"""테스트용 Holding 생성기. 숫자는 손으로 검산하기 쉬운 값을 쓴다."""

from datetime import UTC, datetime
from decimal import Decimal as D

from app.schemas.portfolio import AssetClass, AssetType, FxRate, Position, Quote, Source
from app.services.analytics import apply_weights
from app.services.valuation import build_holding

NOW = datetime(2026, 10, 30, tzinfo=UTC)
USD_KRW = FxRate(
    base_currency="USD", quote_currency="KRW", rate=D("1000"), as_of=NOW, source=Source.MOCK
)


def make(
    symbol: str,
    price: str | None = "100",
    quantity: str = "1",
    cost: str = "100",
    *,
    market: str = "KRX",
    currency: str = "KRW",
    asset_type: AssetType = AssetType.STOCK,
    asset_class: AssetClass = AssetClass.DOMESTIC_STOCK,
    exposure_country: str | None = "KR",
    sector: str | None = None,
    benchmark: str | None = None,
    fx: list[FxRate] | None = None,
):
    position = Position(
        symbol=symbol,
        market=market,
        asset_type=asset_type,
        asset_class=asset_class,
        name=f"{symbol} 이름",
        quantity=D(quantity),
        average_cost=D(cost),
        currency=currency,
        country="KR",
        exposure_country=exposure_country,
        sector=sector,
        benchmark=benchmark,
    )
    quote = Quote(
        symbol=symbol,
        market=market,
        price=D(price) if price is not None else None,
        currency=currency,
        as_of=NOW,
        source=Source.MOCK,
        is_demo=True,
    )
    return build_holding(position, quote, [USD_KRW] if fx is None else fx, "KRW", Source.MOCK, True)


def etf(symbol: str, price: str = "100", benchmark: str | None = None, **kwargs):
    return make(
        symbol,
        price,
        asset_type=AssetType.ETF,
        asset_class=kwargs.pop("asset_class", AssetClass.BROAD_INDEX_ETF),
        benchmark=benchmark,
        **kwargs,
    )


def weighted(*holdings):
    return apply_weights(list(holdings))
