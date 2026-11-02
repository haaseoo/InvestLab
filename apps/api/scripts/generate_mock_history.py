"""data/mock/history.json 생성기. portfolio.json을 바꾼 뒤 다시 실행한다.

    .venv/bin/python scripts/generate_mock_history.py

가상 이력이며 실제 실적이 아니다. 마지막 시점은 현재 Mock 합계와 정확히 일치한다.
"""

import asyncio
import json
import random
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import REPO_ROOT
from app.providers.mock import MockPortfolioProvider
from app.services.analytics import compute_summary

WEEKS = 26
CENT = Decimal("0.01")


async def main() -> None:
    data_dir = REPO_ROOT / "data" / "mock"
    provider = MockPortfolioProvider(data_dir)
    holdings = await provider.get_holdings("KRW")
    summary = compute_summary(holdings, "KRW")
    end = provider._seed.meta.as_of

    rng = random.Random(42)  # noqa: S311 - 재현 가능한 시연 데이터 전용
    points = []
    for i in range(WEEKS):
        progress = Decimal(i) / Decimal(WEEKS - 1)
        # 원금은 8주마다 단계적으로 늘고, 평가금액은 원금 대비 비율이 완만히 오른다.
        step = Decimal(i // 8 + 1) / Decimal((WEEKS - 1) // 8 + 1)
        cost = summary.total_cost_basis * (Decimal("0.70") + Decimal("0.30") * step)
        current_ratio = summary.total_market_value / summary.total_cost_basis
        noise = Decimal(str(round(rng.uniform(-0.02, 0.02), 4))) if i < WEEKS - 1 else Decimal(0)
        ratio = Decimal("1.02") + (current_ratio - Decimal("1.02")) * progress + noise
        points.append(
            {
                "captured_at": (end - timedelta(weeks=WEEKS - 1 - i)).isoformat(),
                "total_market_value": str((cost * ratio).quantize(CENT, ROUND_HALF_UP)),
                "total_cost_basis": str(cost.quantize(CENT, ROUND_HALF_UP)),
                "valuation_currency": "KRW",
            }
        )

    output = {
        "notice": "시연용 가상 이력입니다. 실제 투자 실적이 아닙니다.",
        "points": points,
    }
    with (data_dir / "history.json").open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    asyncio.run(main())
