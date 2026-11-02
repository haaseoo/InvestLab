/** 색은 순위가 아니라 자산군에 고정한다. 비중 순서가 바뀌어도 색이 바뀌지 않는다. */
export const ASSET_CLASS_COLORS: Record<string, string> = {
  broad_index_etf: "var(--chart-1)",
  sector_etf: "var(--chart-2)",
  domestic_stock: "var(--chart-3)",
  overseas_stock: "var(--chart-4)",
  other: "var(--chart-5)",
};

export const FALLBACK_CHART_COLOR = "var(--text-secondary)";
