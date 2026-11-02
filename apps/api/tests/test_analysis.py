"""Phase 2 분석 함수 단위 테스트: 국가·섹터 비중, HHI, ETF 중복, 인사이트."""

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.schemas.analysis import EtfComposition, EtfConstituent
from app.schemas.portfolio import AssetClass
from app.services.analytics import (
    compute_allocation,
    compute_concentration,
)
from app.services.insights import build_insights
from app.services.overlap import (
    analyze_constituent_overlap,
    analyze_overlap,
    find_benchmark_groups,
)
from tests.factories import etf, make, weighted

NOW = datetime(2026, 10, 30, tzinfo=UTC)


def composition(symbol, *constituents, market="KRX"):
    return EtfComposition(
        etf_symbol=symbol,
        etf_market=market,
        as_of=NOW,
        provider="테스트",
        constituents=[
            EtfConstituent(symbol=s, market=m, name=s, weight_pct=D(w)) for s, m, w in constituents
        ],
    )


class TestCountryAndSector:
    def test_unclassified_is_separate_and_last(self):
        holdings = [
            make("A", "100", sector="반도체"),
            make("B", "300", sector=None),
            make("C", "50", sector="반도체"),
            make("D", "50", sector="인터넷"),
        ]
        slices = compute_allocation(holdings, "sector")
        assert [(s.key, s.weight_pct, s.is_unclassified) for s in slices] == [
            ("반도체", D("30"), False),
            ("인터넷", D("10"), False),
            ("unclassified", D("60"), True),  # 가장 커도 마지막
        ]
        assert slices[-1].label == "섹터 정보 없음"
        assert slices[0].symbols == ["A", "C"]

    def test_exposure_country_uses_exposure_not_listing(self):
        holdings = [
            make("KR_LISTED_US_ETF", "300", exposure_country="US"),
            make("KR_STOCK", "100", exposure_country="KR"),
        ]
        slices = compute_allocation(holdings, "exposure_country")
        assert [(s.label, s.weight_pct) for s in slices] == [("미국", D("75")), ("한국", D("25"))]

    def test_unknown_country_code_keeps_code(self):
        slices = compute_allocation([make("A", exposure_country="DE")], "exposure_country")
        assert slices[0].label == "DE"

    def test_unvalued_not_classified(self):
        slices = compute_allocation([make("A", "100"), make("B", None)], "sector")
        assert sum(s.holding_count for s in slices) == 1


class TestHhi:
    def test_equal_weights(self):
        c = compute_concentration(weighted(*[make(str(i), "100") for i in range(4)]))
        assert c.hhi == D("2500")  # 25² × 4
        assert c.effective_holdings == D("4")

    def test_single_holding(self):
        c = compute_concentration(weighted(make("A")))
        assert c.hhi == D("10000")
        assert c.effective_holdings == D("1")

    def test_uneven(self):
        c = compute_concentration(weighted(make("A", "60"), make("B", "40")))
        assert c.hhi == D("5200")  # 3600 + 1600

    def test_no_values(self):
        c = compute_concentration(weighted(make("A", None)))
        assert c.hhi is None
        assert c.effective_holdings is None


class TestBenchmarkGroups:
    def test_groups_two_or_more_same_benchmark(self):
        holdings = weighted(
            etf("VOO", "300", "S&P 500"),
            etf("360750", "100", "S&P 500"),
            etf("QQQ", "100", "NASDAQ-100"),
            etf("NOBENCH", "100", None),
            make("STOCK", "400"),
        )
        groups = find_benchmark_groups(holdings)
        assert len(groups) == 1
        assert groups[0].benchmark == "S&P 500"
        assert [h.symbol for h in groups[0].holdings] == ["VOO", "360750"]
        assert groups[0].combined_weight_pct == D("40")

    def test_stock_with_benchmark_ignored(self):
        holdings = weighted(make("A", benchmark="X"), make("B", benchmark="X"))
        assert find_benchmark_groups(holdings) == []

    def test_unvalued_etf_excluded(self):
        holdings = weighted(etf("A", "100", "X"), etf("B", None, "X"))
        assert find_benchmark_groups(holdings) == []


class TestConstituentOverlap:
    def test_no_etf_is_not_applicable(self):
        result = analyze_constituent_overlap(weighted(make("A")), [])
        assert result.status == "not_applicable"

    def test_no_data_is_unavailable_and_computes_nothing(self):
        result = analyze_constituent_overlap(weighted(etf("E1"), etf("E2")), [])
        assert result.status == "unavailable"
        assert result.missing_etfs == ["E1", "E2"]
        assert result.overlaps == []

    def test_direct_plus_etf_overlap(self):
        holdings = weighted(make("NVDA", "200", market="NASDAQ"), etf("E1", "1000"))
        comp = composition("E1", ("NVDA", "NASDAQ", "10"), ("AAPL", "NASDAQ", "20"))
        result = analyze_constituent_overlap(holdings, [comp])
        assert result.status == "complete"
        assert len(result.overlaps) == 1  # AAPL은 경로가 하나라 중복이 아님
        nvda = result.overlaps[0]
        assert nvda.symbol == "NVDA"
        assert nvda.total_value == D("300")  # 직접 200 + ETF 1000 × 10%
        assert nvda.weight_pct == D("25")  # 300 / 1200
        assert {p.via: p.market_value for p in nvda.paths} == {"direct": D("200"), "E1": D("100")}

    def test_two_etfs_same_constituent(self):
        holdings = weighted(etf("E1", "1000"), etf("E2", "500"))
        comps = [
            composition("E1", ("MSFT", "NASDAQ", "8")),
            composition("E2", ("MSFT", "NASDAQ", "4")),
        ]
        result = analyze_constituent_overlap(holdings, comps)
        assert result.overlaps[0].total_value == D("100")  # 80 + 20

    def test_partial_lists_missing(self):
        holdings = weighted(make("NVDA", "200", market="NASDAQ"), etf("E1", "1000"), etf("E2"))
        result = analyze_constituent_overlap(
            holdings, [composition("E1", ("NVDA", "NASDAQ", "10"))]
        )
        assert result.status == "partial"
        assert result.covered_etfs == ["E1"]
        assert result.missing_etfs == ["E2"]

    def test_constituent_without_market_matches_unique_symbol(self):
        holdings = weighted(make("NVDA", "200", market="NASDAQ"), etf("E1", "1000"))
        result = analyze_constituent_overlap(holdings, [composition("E1", ("NVDA", None, "10"))])
        assert result.overlaps[0].market == "NASDAQ"

    def test_ambiguous_symbol_not_merged(self):
        holdings = weighted(
            make("X", "100", market="KRX"), make("X", "100", market="NYSE"), etf("E1", "1000")
        )
        result = analyze_constituent_overlap(holdings, [composition("E1", ("X", None, "10"))])
        assert result.overlaps == []

    def test_composition_over_100_rejected(self):
        with pytest.raises(ValidationError, match="100%"):
            composition("E1", ("A", None, "60"), ("B", None, "41"))


class TestInsights:
    def _insights(self, holdings, compositions=()):
        holdings = weighted(*holdings)
        allocations = {
            d: compute_allocation(holdings, d)
            for d in ["asset_class", "exposure_country", "sector", "currency"]
        }
        return build_insights(
            holdings,
            compute_concentration(holdings),
            allocations,
            analyze_overlap(holdings, list(compositions)),
            "KRW",
        )

    def test_facts_from_engine(self):
        insights = self._insights(
            [
                etf("VOO", "300", "S&P 500"),
                etf("360750", "100", "S&P 500"),
                make("LOSS", "50", cost="100", sector="반도체"),
                make("GAIN", "50", cost="40", sector=None),
            ]
        )
        titles = [i.title for i in insights]
        assert "상위 3개 종목 비중 90.00%" in titles
        assert "S&P 500 추종 ETF 2개 · 합계 80.00%" in titles
        assert "평가손실 종목 1개" in titles
        assert "ETF 구성 종목 중복은 계산하지 않았습니다" in titles

    def test_no_loser_insight_without_losses(self):
        keys = [i.key for i in self._insights([make("A", "120"), make("B", "130")])]
        assert "losers" not in keys
        assert "etf_data" not in keys  # ETF가 없으면 데이터 한계 문구도 없다

    def test_no_judgment_words(self):
        text = " ".join(
            f"{i.title} {i.detail}"
            for i in self._insights([etf("A", "900", "X"), etf("B", "100", "X")])
        )
        for word in ["위험", "추천", "매수하세요", "매도하세요", "예상", "AI"]:
            assert word not in text

    def test_foreign_currency_insight(self):
        insights = self._insights(
            [
                make("US", "1", currency="USD", asset_class=AssetClass.OVERSEAS_STOCK),
                make("KR", "1000"),
            ]
        )
        assert any(i.key == "currency:USD" and "50.00%" in i.title for i in insights)
