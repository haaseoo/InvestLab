"""포트폴리오 위험 분석 응답 조립."""

from app.providers.base import PortfolioProvider
from app.schemas.analysis import RiskResponse, UnavailableMetric
from app.services.analytics import (
    ASSUMPTIONS,
    apply_weights,
    compute_allocation,
    compute_concentration,
)
from app.services.insights import build_insights
from app.services.overlap import analyze_overlap
from app.services.portfolio import build_meta

RISK_DIMENSIONS = ["asset_class", "exposure_country", "sector", "currency"]

RISK_ASSUMPTIONS = [
    *ASSUMPTIONS,
    "집중도와 비중은 보유 종목 단위입니다. ETF 내부 편입 종목은 구성 종목 데이터가 있을 때만 "
    "펼쳐서 계산합니다.",
    "국가는 투자 대상 국가 기준입니다. 국내 상장 해외지수 ETF는 추종 지수의 국가로 분류합니다.",
    "섹터 정보가 없는 자산은 추정하지 않고 '섹터 정보 없음'으로 따로 표시합니다.",
    "통화 비중은 거래 통화 기준이며 환헤지 여부와 원화 ETF의 환 노출을 반영하지 않습니다.",
]

# 가격 이력이 필요한 지표. 실제 이력이 쌓이기 전에는 계산하지 않는다.
UNAVAILABLE_METRICS = [
    UnavailableMetric(
        key="volatility",
        label="변동성",
        reason="실제 가격 이력이 없습니다. Mock 이력은 가상 데이터라 위험 지표 계산에 쓰지 않습니다.",
    ),
    UnavailableMetric(
        key="max_drawdown",
        label="최대 낙폭(MDD)",
        reason="실제 포트폴리오 스냅샷이 충분히 쌓인 뒤 계산합니다.",
    ),
    UnavailableMetric(
        key="sharpe_ratio",
        label="샤프 지수",
        reason="실제 수익률 이력과 무위험 수익률 데이터가 필요합니다.",
    ),
    UnavailableMetric(
        key="beta",
        label="베타",
        reason="비교 지수의 가격 이력 데이터가 필요합니다.",
    ),
]


async def get_risk(provider: PortfolioProvider, currency: str) -> RiskResponse:
    holdings = apply_weights(await provider.get_holdings(currency))
    compositions = await provider.get_etf_compositions()

    concentration = compute_concentration(holdings)
    allocations = {d: compute_allocation(holdings, d) for d in RISK_DIMENSIONS}
    overlap = analyze_overlap(holdings, compositions)

    return RiskResponse(
        **build_meta(provider, holdings, currency),
        concentration=concentration,
        allocations=allocations,
        overlap=overlap,
        unavailable_metrics=UNAVAILABLE_METRICS,
        insights=build_insights(holdings, concentration, allocations, overlap, currency),
        excluded_symbols=[h.symbol for h in holdings if h.market_value_valuation is None],
        assumptions=RISK_ASSUMPTIONS,
    )
