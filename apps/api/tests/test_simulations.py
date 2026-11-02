"""시뮬레이션 단위 테스트. 기대값은 손으로 계산한 Decimal이다."""

from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.core.errors import HoldingNotFoundError, SimulationInputError
from app.schemas.analysis import BuyRequest, RebalanceRequest, ScenarioRequest
from app.schemas.portfolio import AssetClass
from app.services.simulations import simulate_buy, simulate_rebalance, simulate_scenario
from tests.factories import make, weighted


def portfolio():
    """KR: 10주 × 1000 = 10,000원 (평단 800)
    US: 2주 × $5 × 1000 = 10,000원 (평단 $4)
    총 20,000원, 각 50%"""
    return weighted(
        make("KR", "1000", quantity="10", cost="800"),
        make(
            "US",
            "5",
            quantity="2",
            cost="4",
            market="NASDAQ",
            currency="USD",
            asset_class=AssetClass.OVERSEAS_STOCK,
        ),
    )


def buy(**kwargs):
    defaults = {"symbol": "KR", "market": "KRX", "mode": "quantity", "price": "900"}
    return BuyRequest(**{**defaults, **kwargs})


class TestBuy:
    def test_quantity_mode(self):
        r = simulate_buy(portfolio(), buy(quantity="10"), "KRW")
        assert r["after"].quantity == D("20")
        assert r["after"].cost_basis == D("17000")  # 8000 + 9000
        assert r["after"].average_cost == D("850")
        # 추가분도 현재가 1000으로 평가: 20 × 1000
        assert r["after"].market_value_valuation == D("20000")
        assert r["total_market_value_after"] == D("30000")
        assert r["after"].weight_pct == D("20000") / D("30000") * 100
        us = next(w for w in r["weights"] if w.key == "NASDAQ:US")
        assert us.before_pct == D("50")
        assert us.after_pct == D("10000") / D("30000") * 100

    def test_amount_mode_floors_and_reports_leftover(self):
        r = simulate_buy(portfolio(), buy(mode="amount", amount="2500"), "KRW")
        assert r["purchase"].quantity == D("2")
        assert r["purchase"].leftover_amount == D("700")

    def test_amount_mode_fractional(self):
        r = simulate_buy(
            portfolio(), buy(mode="amount", amount="450", allow_fractional=True), "KRW"
        )
        assert r["purchase"].quantity == D("0.5")
        assert r["purchase"].leftover_amount == D("0")

    def test_amount_smaller_than_one_share(self):
        with pytest.raises(SimulationInputError):
            simulate_buy(portfolio(), buy(mode="amount", amount="500"), "KRW")

    def test_fee_and_tax_only_in_cash_required(self):
        r = simulate_buy(portfolio(), buy(quantity="10", fee_amount="15", tax_amount="5"), "KRW")
        assert r["purchase"].total_cash_required == D("9020")
        assert r["after"].average_cost == D("850")  # 수수료 미포함
        assert "수수료를 적용했습니다." in r["assumptions"]

    def test_fee_not_applied_is_stated(self):
        r = simulate_buy(portfolio(), buy(quantity="1"), "KRW")
        assert r["purchase"].fee_amount is None
        assert "수수료는 적용하지 않았습니다." in r["assumptions"]
        assert "세금은 적용하지 않았습니다." in r["assumptions"]

    def test_foreign_uses_current_fx_by_default(self):
        r = simulate_buy(
            portfolio(), buy(symbol="US", market="NASDAQ", quantity="2", price="6"), "KRW"
        )
        p = r["purchase"]
        assert p.fx_rate_source == "current"
        assert p.total_cash_required == D("12")
        assert p.total_cash_required_valuation == D("12000")
        assert r["after"].average_cost == D("5")  # (8 + 12) / 4
        assert r["after"].cost_basis_valuation == D("8000") + D("12000")

    def test_foreign_with_input_fx(self):
        r = simulate_buy(
            portfolio(),
            buy(symbol="US", market="NASDAQ", quantity="2", price="6", fx_rate="1100"),
            "KRW",
        )
        assert r["purchase"].fx_rate_source == "input"
        assert r["after"].cost_basis_valuation == D("8000") + D("13200")
        # 평가는 여전히 현재 환율 1000: 4주 × $5 × 1000
        assert r["after"].market_value_valuation == D("20000")

    def test_fractional_quantity_requires_flag(self):
        with pytest.raises(ValidationError):
            buy(quantity="0.5")
        assert buy(quantity="0.5", allow_fractional=True).quantity == D("0.5")

    def test_unknown_holding(self):
        with pytest.raises(HoldingNotFoundError):
            simulate_buy(portfolio(), buy(symbol="NONE", quantity="1"), "KRW")

    def test_holding_without_price_has_no_after_value(self):
        holdings = weighted(make("KR", None, quantity="10", cost="800"), make("B", "100"))
        r = simulate_buy(holdings, buy(quantity="1"), "KRW")
        assert r["after"].quantity == D("11")
        assert r["after"].market_value_valuation is None
        assert r["after"].weight_pct is None
        assert r["total_market_value_after"] is None

    def test_mode_field_required(self):
        with pytest.raises(ValidationError):
            BuyRequest(symbol="KR", market="KRX", mode="amount", price="1")


def rebalance(targets, dimension="holding", cash="0"):
    return RebalanceRequest(
        dimension=dimension,
        targets=[{"key": k, "target_pct": v} for k, v in targets.items()],
        additional_cash=cash,
    )


class TestRebalance:
    def test_holding_targets(self):
        r = simulate_rebalance(portfolio(), rebalance({"KRX:KR": "70", "NASDAQ:US": "30"}))
        rows = {row.key: row for row in r["rows"]}
        assert rows["KRX:KR"].target_value == D("14000")
        assert rows["KRX:KR"].adjustment_value == D("4000")
        assert rows["KRX:KR"].diff_pct == D("20")
        assert rows["KRX:KR"].theoretical_quantity == D("4")  # 4000 / 1000
        assert rows["NASDAQ:US"].adjustment_value == D("-4000")
        assert rows["NASDAQ:US"].theoretical_quantity == D("-0.8")  # -4000 / (5 × 1000)
        assert rows["NASDAQ:US"].price_currency == "USD"

    def test_adjustments_sum_to_additional_cash(self):
        r = simulate_rebalance(
            portfolio(), rebalance({"KRX:KR": "50", "NASDAQ:US": "50"}, cash="10000")
        )
        assert r["total_after"] == D("30000")
        assert sum(row.adjustment_value for row in r["rows"]) == D("10000")

    def test_implicit_zero_target(self):
        r = simulate_rebalance(portfolio(), rebalance({"KRX:KR": "100"}))
        us = next(row for row in r["rows"] if row.key == "NASDAQ:US")
        assert us.implicit_target is True
        assert us.target_pct == 0
        assert us.adjustment_value == D("-10000")
        assert any("0%" in a for a in r["assumptions"])

    def test_asset_class_dimension(self):
        r = simulate_rebalance(
            portfolio(),
            rebalance({"domestic_stock": "40", "overseas_stock": "60"}, dimension="asset_class"),
        )
        rows = {row.key: row for row in r["rows"]}
        assert rows["overseas_stock"].adjustment_value == D("2000")
        assert rows["overseas_stock"].theoretical_quantity is None
        assert rows["overseas_stock"].label == "해외 개별주"

    @pytest.mark.parametrize(
        "targets",
        [
            {"KRX:KR": "60", "NASDAQ:US": "30"},  # 합 90
            {"KRX:KR": "100", "NOPE": "0"},  # 모르는 키
        ],
    )
    def test_invalid_targets(self, targets):
        with pytest.raises(SimulationInputError):
            simulate_rebalance(portfolio(), rebalance(targets))

    def test_duplicate_key(self):
        request = RebalanceRequest(
            dimension="holding",
            targets=[{"key": "KRX:KR", "target_pct": "50"}, {"key": "KRX:KR", "target_pct": "50"}],
        )
        with pytest.raises(SimulationInputError):
            simulate_rebalance(portfolio(), request)

    def test_sum_tolerance(self):
        simulate_rebalance(portfolio(), rebalance({"KRX:KR": "50.005", "NASDAQ:US": "50"}))

    def test_unvalued_holding_cannot_be_targeted(self):
        holdings = weighted(make("A", "100"), make("B", None))
        with pytest.raises(SimulationInputError):
            simulate_rebalance(holdings, rebalance({"KRX:A": "50", "KRX:B": "50"}))

    def test_marked_theoretical(self):
        r = simulate_rebalance(portfolio(), rebalance({"KRX:KR": "50", "NASDAQ:US": "50"}))
        assert "수수료와 세금" in r["constraints_not_applied"]


def scenario(**kwargs):
    return ScenarioRequest(**kwargs)


class TestScenario:
    def test_asset_class_shock(self):
        r = simulate_scenario(
            portfolio(),
            scenario(
                shocks=[{"type": "asset_class", "key": "overseas_stock", "change_pct": "-30"}]
            ),
            "KRW",
        )
        assert r["total_after"] == D("17000")
        assert r["total_change"] == D("-3000")
        assert r["total_change_pct"] == D("-15")
        us = next(row for row in r["rows"] if row.symbol == "US")
        assert us.price_change_source == "asset_class"
        assert us.impact_on_total_pct == D("-15")

    def test_holding_overrides_asset_class_without_compounding(self):
        holdings = weighted(make("A", "100"), make("B", "100"))
        r = simulate_scenario(
            holdings,
            scenario(
                shocks=[
                    {"type": "asset_class", "key": "domestic_stock", "change_pct": "-10"},
                    {"type": "holding", "key": "KRX:A", "change_pct": "-50"},
                ]
            ),
            "KRW",
        )
        rows = {row.symbol: row for row in r["rows"]}
        assert rows["A"].value_after == D("50")  # -50%만, -55%가 아님
        assert rows["B"].value_after == D("90")

    def test_fx_shock_applies_to_currency_only(self):
        r = simulate_scenario(
            portfolio(), scenario(fx_shocks=[{"currency": "USD", "change_pct": "-10"}]), "KRW"
        )
        rows = {row.symbol: row for row in r["rows"]}
        assert rows["US"].value_after == D("9000")
        assert rows["KR"].value_after == D("10000")

    def test_price_and_fx_compound(self):
        r = simulate_scenario(
            portfolio(),
            scenario(
                shocks=[{"type": "holding", "key": "NASDAQ:US", "change_pct": "-20"}],
                fx_shocks=[{"currency": "USD", "change_pct": "-10"}],
            ),
            "KRW",
        )
        us = next(row for row in r["rows"] if row.symbol == "US")
        assert us.value_after == D("7200")  # 10000 × 0.8 × 0.9

    def test_minus_100_is_zero(self):
        r = simulate_scenario(
            portfolio(),
            scenario(shocks=[{"type": "holding", "key": "KRX:KR", "change_pct": "-100"}]),
            "KRW",
        )
        assert next(row for row in r["rows"] if row.symbol == "KR").value_after == 0

    def test_standalone_sensitivity(self):
        holdings = weighted(make("BIG", "300"), make("SMALL", "100"))
        r = simulate_scenario(holdings, scenario(standalone_change_pct="-20"), "KRW")
        assert [(s.symbol, s.impact, s.impact_on_total_pct) for s in r["standalone"]] == [
            ("BIG", D("-60"), D("-15")),
            ("SMALL", D("-20"), D("-5")),
        ]
        assert r["total_change"] == 0  # standalone만 지정하면 전체 시나리오는 변화 없음

    def test_rows_sorted_by_loss(self):
        r = simulate_scenario(
            portfolio(),
            scenario(shocks=[{"type": "holding", "key": "NASDAQ:US", "change_pct": "-50"}]),
            "KRW",
        )
        assert r["rows"][0].symbol == "US"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"shocks": [{"type": "holding", "key": "KRX:NONE", "change_pct": "-10"}]},
            {"fx_shocks": [{"currency": "KRW", "change_pct": "-10"}]},
            {
                "fx_shocks": [
                    {"currency": "USD", "change_pct": "-10"},
                    {"currency": "USD", "change_pct": "-5"},
                ]
            },
        ],
    )
    def test_invalid_input(self, kwargs):
        with pytest.raises(SimulationInputError):
            simulate_scenario(portfolio(), scenario(**kwargs), "KRW")

    def test_empty_request_rejected(self):
        with pytest.raises(ValidationError):
            ScenarioRequest()

    def test_below_minus_100_rejected(self):
        with pytest.raises(ValidationError):
            scenario(shocks=[{"type": "holding", "key": "KRX:KR", "change_pct": "-101"}])
