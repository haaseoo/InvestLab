"""ETF 중복 투자 분석.

두 가지를 구분한다.
1. 동일 지수 추종(benchmark_groups): 추종 지수 메타데이터가 같은 ETF 묶음. 구성 종목 데이터 없이
   알 수 있는 사실이지만, 실제로 어느 종목에 얼마나 겹치는지는 말해 주지 않는다.
2. 구성 종목 중복(constituent_overlap): ETF 구성 종목을 펼쳐(look-through) 같은 기초 종목에
   두 경로 이상으로 노출된 금액을 계산한다. 구성 종목 데이터가 있는 ETF만 반영하며, 데이터가
   없으면 계산하지 않는다.
"""

from decimal import Decimal

from app.schemas.analysis import (
    BenchmarkGroup,
    ConstituentOverlap,
    EtfComposition,
    ExposurePath,
    HoldingRef,
    LookThroughExposure,
    OverlapAnalysis,
)
from app.schemas.portfolio import AssetType, Holding
from app.services.analytics import valued_holdings

HUNDRED = Decimal(100)
DIRECT = "direct"


def find_benchmark_groups(holdings: list[Holding]) -> list[BenchmarkGroup]:
    """추종 지수가 같은 ETF가 2개 이상인 묶음. combined_weight_pct = 묶음 내 weight_pct 합.

    apply_weights를 거친 Holding을 받으며, 평가금액을 알 수 없는 ETF는 제외한다.
    """
    groups: dict[str, list[Holding]] = {}
    for h in holdings:
        if h.asset_type is AssetType.ETF and h.benchmark and h.weight_pct is not None:
            groups.setdefault(h.benchmark, []).append(h)

    result = [
        BenchmarkGroup(
            benchmark=benchmark,
            holdings=[
                HoldingRef(symbol=h.symbol, market=h.market, name=h.name, weight_pct=h.weight_pct)
                for h in members
            ],
            combined_weight_pct=sum((h.weight_pct for h in members), Decimal(0)),
        )
        for benchmark, members in groups.items()
        if len(members) >= 2
    ]
    return sorted(result, key=lambda g: g.combined_weight_pct, reverse=True)


def analyze_constituent_overlap(
    holdings: list[Holding], compositions: list[EtfComposition]
) -> ConstituentOverlap:
    """look-through 노출 = 직접 보유 평가금액 + Σ(ETF 평가금액 × 구성 비중 ÷ 100)

    두 경로 이상(직접 + ETF, 또는 ETF 2개 이상)으로 노출된 기초 종목만 overlaps에 담는다.
    weight_pct는 포트폴리오 전체 평가금액 대비 비중이다.

    기초 종목 식별: 구성 종목에 시장 정보가 있으면 (종목코드, 시장)으로, 없으면 같은 종목코드의
    직접 보유 종목이 정확히 하나일 때만 그 종목과 묶는다. 애매하면 묶지 않는다.
    """
    valued = valued_holdings(holdings)
    etfs = [h for h in valued if h.asset_type is AssetType.ETF]
    if not etfs:
        return ConstituentOverlap(
            status="not_applicable", covered_etfs=[], missing_etfs=[], overlaps=[]
        )

    by_etf = {(c.etf_symbol, c.etf_market): c for c in compositions}
    covered = [e for e in etfs if (e.symbol, e.market) in by_etf]
    missing = [e.symbol for e in etfs if (e.symbol, e.market) not in by_etf]
    if not covered:
        return ConstituentOverlap(
            status="unavailable", covered_etfs=[], missing_etfs=missing, overlaps=[]
        )

    total = sum((h.market_value_valuation for h in valued), Decimal(0))
    direct_by_symbol: dict[str, list[Holding]] = {}
    for h in valued:
        direct_by_symbol.setdefault(h.symbol, []).append(h)

    exposures: dict[tuple[str, str | None], dict] = {}

    def add(key: tuple[str, str | None], name: str, via: str, value: Decimal) -> None:
        entry = exposures.setdefault(key, {"name": name, "paths": {}})
        entry["paths"][via] = entry["paths"].get(via, Decimal(0)) + value

    for h in valued:
        add((h.symbol, h.market), h.name, DIRECT, h.market_value_valuation)

    for etf in covered:
        for c in by_etf[(etf.symbol, etf.market)].constituents:
            if c.market is not None:
                key = (c.symbol, c.market)
            else:
                matches = direct_by_symbol.get(c.symbol, [])
                key = (c.symbol, matches[0].market) if len(matches) == 1 else (c.symbol, None)
            add(key, c.name, etf.symbol, etf.market_value_valuation * c.weight_pct / HUNDRED)

    overlaps = []
    for (symbol, market), entry in exposures.items():
        if len(entry["paths"]) < 2:
            continue
        value = sum(entry["paths"].values(), Decimal(0))
        overlaps.append(
            LookThroughExposure(
                symbol=symbol,
                market=market,
                name=entry["name"],
                total_value=value,
                weight_pct=value / total * HUNDRED,
                paths=[ExposurePath(via=v, market_value=m) for v, m in entry["paths"].items()],
            )
        )

    return ConstituentOverlap(
        status="partial" if missing else "complete",
        covered_etfs=[e.symbol for e in covered],
        missing_etfs=missing,
        overlaps=sorted(overlaps, key=lambda o: o.total_value, reverse=True),
    )


def analyze_overlap(holdings: list[Holding], compositions: list[EtfComposition]) -> OverlapAnalysis:
    return OverlapAnalysis(
        benchmark_groups=find_benchmark_groups(holdings),
        constituent_overlap=analyze_constituent_overlap(holdings, compositions),
    )
