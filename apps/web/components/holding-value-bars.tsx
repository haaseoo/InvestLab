import { formatMoney, formatPercent } from "@/lib/format";
import type { Holding } from "@/types/portfolio";

/** 종목별 평가금액. 값을 막대 옆에 직접 표기해 범례·툴팁 없이 읽을 수 있다. */
export function HoldingValueBars({ holdings, limit }: { holdings: Holding[]; limit?: number }) {
  const sorted = holdings
    .filter((h) => h.market_value_valuation !== null)
    .sort((a, b) => Number(b.market_value_valuation) - Number(a.market_value_valuation));
  const valued = limit ? sorted.slice(0, limit) : sorted;
  const max = Number(valued[0]?.market_value_valuation ?? 0);
  const unvalued = holdings.filter((h) => h.market_value_valuation === null);

  return (
    <div>
      <ul className="space-y-3.5">
        {valued.map((h) => (
          <li key={`${h.market}:${h.symbol}`}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate font-medium">{h.name}</span>
              <span className="shrink-0 num">
                <span className="font-semibold">
                  {formatMoney(h.market_value_valuation, h.valuation_currency)}
                </span>
                <span className="ml-2 inline-block w-14 text-right text-[13px] text-subtle">
                  {formatPercent(h.weight_pct)}
                </span>
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-chart-1"
                style={{
                  width: `${max > 0 ? (Number(h.market_value_valuation) / max) * 100 : 0}%`,
                }}
              />
            </div>
          </li>
        ))}
      </ul>
      {unvalued.length > 0 && (
        <p className="mt-4 text-[13px] text-subtle">
          시세를 조회하지 못해 제외: {unvalued.map((h) => h.name).join(", ")}
        </p>
      )}
    </div>
  );
}
