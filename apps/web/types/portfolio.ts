/** API의 금액·비율은 정밀도 보존을 위해 문자열이다. null은 "값을 알 수 없음"이며 0이 아니다. */
export type DecimalString = string;
export type Source = "mock" | "live";
export type ValuationStatus = "reported" | "calculated" | "unavailable";

export interface Holding {
  symbol: string;
  market: string;
  asset_type: "stock" | "etf" | "other";
  asset_class: string;
  name: string;
  country: string | null;
  sector: string | null;
  quantity: DecimalString;
  average_cost: DecimalString;
  current_price: DecimalString | null;
  currency: string;
  cost_basis: DecimalString;
  market_value: DecimalString | null;
  unrealized_pnl: DecimalString | null;
  unrealized_pnl_pct: DecimalString | null;
  valuation_currency: string;
  fx_rate: DecimalString | null;
  fx_as_of: string | null;
  cost_basis_valuation: DecimalString | null;
  market_value_valuation: DecimalString | null;
  unrealized_pnl_valuation: DecimalString | null;
  weight_pct: DecimalString | null;
  valuation_status: ValuationStatus;
  as_of: string | null;
  source: Source;
  is_demo: boolean;
}

export interface PortfolioSummary {
  valuation_currency: string;
  total_cost_basis: DecimalString | null;
  total_market_value: DecimalString | null;
  valued_cost_basis: DecimalString | null;
  total_unrealized_pnl: DecimalString | null;
  total_unrealized_pnl_pct: DecimalString | null;
  holding_count: number;
  valued_holding_count: number;
  unvalued_symbols: string[];
  is_complete: boolean;
}

export interface AllocationSlice {
  key: string;
  label: string;
  market_value: DecimalString;
  weight_pct: DecimalString;
  holding_count: number;
}

export interface Concentration {
  top1_pct: DecimalString | null;
  top3_pct: DecimalString | null;
  top5_pct: DecimalString | null;
}

export interface FxRate {
  base_currency: string;
  quote_currency: string;
  rate: DecimalString;
  as_of: string;
  source: Source;
}

export interface Portfolio {
  source: Source;
  is_demo: boolean;
  as_of: string | null;
  retrieved_at: string;
  valuation_currency: string;
  summary: PortfolioSummary;
  concentration: Concentration;
  assumptions: string[];
  fx_rates: FxRate[];
  holdings: Holding[];
  allocation: AllocationSlice[];
}

export interface SnapshotPoint {
  captured_at: string;
  total_market_value: DecimalString;
  total_cost_basis: DecimalString;
  valuation_currency: string;
}

export interface History {
  source: Source;
  is_demo: boolean;
  retrieved_at: string;
  points: SnapshotPoint[];
}

export interface ProviderStatus {
  source: Source;
  state: "ready" | "not_configured" | "not_implemented";
  is_demo: boolean;
  label: string;
  message: string;
  checks: { key: string; label: string; ok: boolean }[];
}

export interface ProvidersStatus {
  default_source: Source;
  providers: ProviderStatus[];
}
