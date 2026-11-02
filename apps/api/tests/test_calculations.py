"""계산 엔진 단위 테스트. 기대값은 손으로 계산한 Decimal 상수다."""

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from app.schemas.portfolio import (
    AssetClass,
    AssetType,
    FxRate,
    Position,
    Quote,
    Source,
    ValuationStatus,
)
from app.services.analytics import (
    apply_weights,
    compute_allocation,
    compute_concentration,
    compute_summary,
)
from app.services.valuation import build_holding

NOW = datetime(2026, 10, 30, tzinfo=UTC)
USD_KRW = FxRate(
    base_currency="USD", quote_currency="KRW", rate=D("1400"), as_of=NOW, source=Source.MOCK
)


def holding(
    symbol="A",
    quantity="10",
    cost="100",
    price: str | None = "120",
    currency="KRW",
    fx=None,
    asset_class=AssetClass.DOMESTIC_STOCK,
    reported=None,
):
    position = Position(
        symbol=symbol,
        market="KRX",
        asset_type=AssetType.STOCK,
        asset_class=asset_class,
        name=symbol,
        quantity=D(quantity),
        average_cost=D(cost),
        currency=currency,
    )
    quote = Quote(
        symbol=symbol,
        market="KRX",
        price=D(price) if price is not None else None,
        currency=currency,
        as_of=NOW if price is not None else None,
        source=Source.MOCK,
        is_demo=True,
    )
    return build_holding(
        position,
        quote,
        [USD_KRW] if fx is None else fx,
        "KRW",
        Source.MOCK,
        True,
        reported_market_value=D(reported) if reported else None,
    )


class TestBuildHolding:
    def test_same_currency(self):
        h = holding()
        assert h.cost_basis == D("1000")
        assert h.market_value == D("1200")
        assert h.unrealized_pnl == D("200")
        assert h.unrealized_pnl_pct == D("20")
        assert h.fx_rate == D("1")
        assert h.market_value_valuation == D("1200")
        assert h.valuation_status is ValuationStatus.CALCULATED

    def test_foreign_currency_is_converted(self):
        h = holding(quantity="2", cost="100", price="150", currency="USD")
        assert h.market_value == D("300")  # 거래 통화 금액은 그대로
        assert h.market_value_valuation == D("420000")
        assert h.cost_basis_valuation == D("280000")
        assert h.unrealized_pnl_valuation == D("140000")
        assert h.fx_as_of == NOW

    def test_decimal_has_no_float_error(self):
        h = holding(quantity="3", cost="0.1", price="0.2")
        assert h.cost_basis == D("0.3")
        assert h.market_value == D("0.6")

    def test_loss_is_negative(self):
        h = holding(price="75")
        assert h.unrealized_pnl == D("-250")
        assert h.unrealized_pnl_pct == D("-25")

    def test_missing_price_is_none_not_zero(self):
        h = holding(price=None)
        assert h.current_price is None
        assert h.market_value is None
        assert h.unrealized_pnl is None
        assert h.unrealized_pnl_pct is None
        assert h.valuation_status is ValuationStatus.UNAVAILABLE
        assert h.cost_basis == D("1000")  # 원금은 시세와 무관하게 안다

    def test_real_zero_price_stays_zero(self):
        h = holding(price="0")
        assert h.market_value == D("0")
        assert h.unrealized_pnl_pct == D("-100")
        assert h.valuation_status is ValuationStatus.CALCULATED

    def test_missing_fx_keeps_native_value_but_no_conversion(self):
        h = holding(currency="USD", fx=[])
        assert h.market_value == D("1200")
        assert h.fx_rate is None
        assert h.market_value_valuation is None
        assert h.cost_basis_valuation is None

    def test_inverse_fx_is_not_guessed(self):
        h = holding(currency="JPY")  # USD/KRW만 있음
        assert h.fx_rate is None

    def test_zero_cost_has_no_pct(self):
        h = holding(cost="0")
        assert h.unrealized_pnl == D("1200")
        assert h.unrealized_pnl_pct is None

    def test_reported_market_value_wins(self):
        h = holding(reported="1234")
        assert h.market_value == D("1234")
        assert h.valuation_status is ValuationStatus.REPORTED

    def test_quote_currency_mismatch_is_rejected(self):
        position = Position(
            symbol="A",
            market="KRX",
            asset_type=AssetType.STOCK,
            asset_class=AssetClass.DOMESTIC_STOCK,
            name="A",
            quantity=D(1),
            average_cost=D(1),
            currency="KRW",
        )
        quote = Quote(
            symbol="A",
            market="KRX",
            price=D(1),
            currency="USD",
            as_of=NOW,
            source=Source.MOCK,
            is_demo=True,
        )
        with pytest.raises(ValueError, match="통화"):
            build_holding(position, quote, [], "KRW", Source.MOCK, True)


class TestSummary:
    def test_krw_and_usd_are_summed_only_after_conversion(self):
        s = compute_summary(
            [
                holding("KR", quantity="10", cost="1000", price="1100"),
                holding("US", quantity="1", cost="100", price="110", currency="USD"),
            ],
            "KRW",
        )
        assert s.total_cost_basis == D("10000") + D("140000")
        assert s.total_market_value == D("11000") + D("154000")
        assert s.total_unrealized_pnl == D("15000")
        assert s.total_unrealized_pnl_pct == D("10")
        assert s.is_complete is True

    def test_unvalued_holding_excluded_from_pnl_denominator(self):
        s = compute_summary(
            [
                holding("OK", quantity="10", cost="100", price="110"),
                holding("NOPRICE", quantity="10", cost="100", price=None),
            ],
            "KRW",
        )
        assert s.total_cost_basis == D("2000")  # 원금은 둘 다 포함
        assert s.valued_cost_basis == D("1000")
        assert s.total_market_value == D("1100")
        assert s.total_unrealized_pnl == D("100")
        assert s.total_unrealized_pnl_pct == D("10")  # 5%가 아니다
        assert s.unvalued_symbols == ["NOPRICE"]
        assert s.is_complete is False

    def test_all_unavailable_is_none_not_zero(self):
        s = compute_summary([holding(price=None)], "KRW")
        assert s.total_market_value is None
        assert s.total_unrealized_pnl is None
        assert s.total_unrealized_pnl_pct is None

    def test_empty_portfolio_is_none(self):
        s = compute_summary([], "KRW")
        assert s.total_market_value is None
        assert s.total_cost_basis is None
        assert s.is_complete is True

    def test_mixed_valuation_currency_is_rejected(self):
        a = holding("A")
        b = holding("B").model_copy(update={"valuation_currency": "USD"})
        with pytest.raises(ValueError, match="평가 통화"):
            compute_summary([a, b], "KRW")


class TestWeightsAndAllocation:
    def test_weights_sum_to_100_and_skip_unvalued(self):
        result = apply_weights(
            [
                holding("A", quantity="1", cost="1", price="300"),
                holding("B", quantity="1", cost="1", price="100"),
                holding("C", quantity="1", cost="1", price=None),
            ]
        )
        assert [h.weight_pct for h in result] == [D("75"), D("25"), None]

    def test_allocation_groups_and_sorts(self):
        holdings = [
            holding("A", quantity="1", cost="1", price="100", asset_class=AssetClass.OTHER),
            holding("B", quantity="1", cost="1", price="200", asset_class=AssetClass.SECTOR_ETF),
            holding("C", quantity="1", cost="1", price="100", asset_class=AssetClass.SECTOR_ETF),
            holding("D", quantity="1", cost="1", price=None, asset_class=AssetClass.OTHER),
        ]
        slices = compute_allocation(holdings, "asset_class")
        assert [(s.key, s.weight_pct, s.holding_count) for s in slices] == [
            ("sector_etf", D("75"), 2),
            ("other", D("25"), 1),
        ]
        assert slices[0].label == "섹터·테마 ETF"

    def test_allocation_without_values_is_empty(self):
        assert compute_allocation([holding(price=None)], "asset_class") == []


class TestConcentration:
    def test_top_n(self):
        holdings = apply_weights(
            [
                holding(str(i), quantity="1", cost="1", price=str(price))
                for i, price in enumerate([50, 20, 10, 10, 5, 5])
            ]
        )
        c = compute_concentration(holdings)
        assert c.top1_pct == D("50")
        assert c.top3_pct == D("80")
        assert c.top5_pct == D("95")

    def test_fewer_than_n(self):
        c = compute_concentration(apply_weights([holding()]))
        assert c.top1_pct == c.top3_pct == c.top5_pct == D("100")

    def test_no_values_is_none(self):
        c = compute_concentration(apply_weights([holding(price=None)]))
        assert c.top1_pct is None
