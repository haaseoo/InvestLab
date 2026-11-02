import { formatMoney, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AllocationSlice } from "@/types/portfolio";

interface AllocationBarsProps {
  slices: AllocationSlice[];
  currency: string;
  /** 막대 색. 분류 정보 없음 묶음은 항상 회색 빗금으로 구분한다. */
  color?: string;
  showSymbols?: boolean;
}

/** 비중 막대 목록. 값과 비중을 글자로 함께 적어 색 없이도 읽을 수 있다. */
export function AllocationBars({
  slices,
  currency,
  color = "var(--chart-1)",
  showSymbols = false,
}: AllocationBarsProps) {
  return (
    <ul className="space-y-3.5">
      {slices.map((slice) => (
        <li key={slice.key}>
          <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
            <span
              className={cn("min-w-0 truncate font-medium", slice.is_unclassified && "text-subtle")}
            >
              {slice.label}
              <span className="ml-1.5 text-xs font-normal text-subtle">
                {slice.holding_count}종목
              </span>
            </span>
            <span className="shrink-0 num">
              <span className="text-[13px] text-subtle">
                {formatMoney(slice.market_value, currency)}
              </span>
              <span className="ml-2 inline-block w-16 text-right font-semibold">
                {formatPercent(slice.weight_pct)}
              </span>
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-secondary">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.min(Number(slice.weight_pct), 100)}%`,
                background: slice.is_unclassified
                  ? "repeating-linear-gradient(135deg, var(--text-secondary) 0 3px, transparent 3px 6px)"
                  : color,
              }}
            />
          </div>
          {showSymbols && (
            <p className="mt-1 truncate text-xs text-subtle">{slice.symbols.join(", ")}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
