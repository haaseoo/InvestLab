import type { AllocationSlice } from "@/types/portfolio";

/** 색은 순위가 아니라 자산군에 고정한다. 비중 순서가 바뀌어도 색이 바뀌지 않는다. */
export const ASSET_CLASS_COLORS: Record<string, string> = {
  broad_index_etf: "var(--chart-1)",
  domestic_stock: "var(--chart-2)",
  overseas_stock: "var(--chart-3)",
  sector_etf: "var(--chart-4)",
  other: "var(--chart-5)",
};

export const FALLBACK_CHART_COLOR = "var(--text-secondary)";

const SECTOR_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)"];
const OTHER_SECTORS_KEY = "__other_sectors";

/**
 * 도넛에 쓸 섹터 조각. 색이 구분되도록 큰 섹터 4개만 따로 두고 나머지는 "기타 섹터"로 묶는다.
 * 섹터 정보가 없는 묶음은 실제 섹터가 아니므로 회색으로 맨 뒤에 둔다. 금액·비중은 표시용 합계다.
 */
export function sectorDonutSlices(slices: AllocationSlice[]): AllocationSlice[] {
  const named = slices.filter((s) => !s.is_unclassified);
  const unclassified = slices.filter((s) => s.is_unclassified);
  const head = named.slice(0, SECTOR_COLORS.length);
  const rest = named.slice(SECTOR_COLORS.length);
  if (rest.length === 1) head.push(rest[0]);
  else if (rest.length > 1) {
    const sum = (pick: (s: AllocationSlice) => string) =>
      rest.reduce((acc, s) => acc + Number(pick(s)), 0);
    head.push({
      key: OTHER_SECTORS_KEY,
      label: `기타 섹터 ${rest.length}개`,
      market_value: sum((s) => s.market_value).toFixed(4),
      weight_pct: sum((s) => s.weight_pct).toFixed(2),
      holding_count: rest.reduce((acc, s) => acc + s.holding_count, 0),
      is_unclassified: false,
      symbols: rest.flatMap((s) => s.symbols),
    });
  }
  return [...head, ...unclassified];
}

export function sectorColor(slice: AllocationSlice, slices: AllocationSlice[]): string {
  if (slice.is_unclassified) return FALLBACK_CHART_COLOR;
  const index = slices.filter((s) => !s.is_unclassified).indexOf(slice);
  return SECTOR_COLORS[index] ?? "var(--chart-5)";
}
