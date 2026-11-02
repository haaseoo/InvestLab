import type { AllocationSlice, Concentration, DecimalString, Source } from "@/types/portfolio";

export interface ResponseMeta {
  source: Source;
  is_demo: boolean;
  as_of: string | null;
  retrieved_at: string;
  valuation_currency: string;
}

export interface Insight {
  key: string;
  title: string;
  detail: string;
}

export interface HoldingRef {
  symbol: string;
  market: string;
  name: string;
  weight_pct: DecimalString;
}

export interface BenchmarkGroup {
  benchmark: string;
  holdings: HoldingRef[];
  combined_weight_pct: DecimalString;
}

export interface LookThroughExposure {
  symbol: string;
  market: string | null;
  name: string;
  total_value: DecimalString;
  weight_pct: DecimalString;
  paths: { via: string; market_value: DecimalString }[];
}

export interface ConstituentOverlap {
  status: "not_applicable" | "unavailable" | "partial" | "complete";
  covered_etfs: string[];
  missing_etfs: string[];
  overlaps: LookThroughExposure[];
}

export interface Risk extends ResponseMeta {
  concentration: Concentration;
  allocations: Record<
    "asset_class" | "exposure_country" | "sector" | "currency",
    AllocationSlice[]
  >;
  overlap: { benchmark_groups: BenchmarkGroup[]; constituent_overlap: ConstituentOverlap };
  unavailable_metrics: { key: string; label: string; reason: string }[];
  insights: Insight[];
  excluded_symbols: string[];
  assumptions: string[];
}

interface SimulationMeta extends ResponseMeta {
  is_theoretical: boolean;
  assumptions: string[];
}

export interface BuyRequest {
  symbol: string;
  market: string;
  mode: "quantity" | "amount";
  quantity?: string;
  amount?: string;
  price: string;
  allow_fractional: boolean;
  fee_amount?: string;
  tax_amount?: string;
  fx_rate?: string;
}

export interface PositionState {
  quantity: DecimalString;
  average_cost: DecimalString;
  cost_basis: DecimalString;
  cost_basis_valuation: DecimalString | null;
  market_value_valuation: DecimalString | null;
  weight_pct: DecimalString | null;
}

export interface BuyResult extends SimulationMeta {
  symbol: string;
  market: string;
  name: string;
  currency: string;
  before: PositionState;
  after: PositionState;
  purchase: {
    quantity: DecimalString;
    price: DecimalString;
    gross_amount: DecimalString;
    fee_amount: DecimalString | null;
    tax_amount: DecimalString | null;
    total_cash_required: DecimalString;
    total_cash_required_valuation: DecimalString | null;
    fx_rate_used: DecimalString | null;
    fx_rate_source: "same_currency" | "input" | "current" | "unavailable";
    leftover_amount: DecimalString | null;
  };
  total_market_value_before: DecimalString | null;
  total_market_value_after: DecimalString | null;
  weights: {
    key: string;
    name: string;
    before_pct: DecimalString | null;
    after_pct: DecimalString | null;
  }[];
}

export interface RebalanceRequest {
  dimension: "holding" | "asset_class";
  targets: { key: string; target_pct: string }[];
  additional_cash: string;
}

export interface RebalanceResult extends SimulationMeta {
  dimension: string;
  total_before: DecimalString;
  additional_cash: DecimalString;
  total_after: DecimalString;
  rows: {
    key: string;
    label: string;
    current_value: DecimalString;
    current_pct: DecimalString;
    target_pct: DecimalString;
    diff_pct: DecimalString;
    target_value: DecimalString;
    adjustment_value: DecimalString;
    theoretical_quantity: DecimalString | null;
    price_currency: string | null;
    implicit_target: boolean;
  }[];
  excluded_symbols: string[];
  constraints_not_applied: string[];
}

export interface ScenarioRequest {
  shocks: { type: "holding" | "asset_class"; key: string; change_pct: string }[];
  fx_shocks: { currency: string; change_pct: string }[];
  standalone_change_pct?: string;
}

export interface ScenarioResult extends SimulationMeta {
  total_before: DecimalString;
  total_after: DecimalString;
  total_change: DecimalString;
  total_change_pct: DecimalString;
  rows: {
    key: string;
    symbol: string;
    name: string;
    asset_class: string;
    value_before: DecimalString;
    price_change_pct: DecimalString;
    price_change_source: "holding" | "asset_class" | "none";
    fx_change_pct: DecimalString;
    value_after: DecimalString;
    impact: DecimalString;
    impact_on_total_pct: DecimalString;
  }[];
  standalone_change_pct: DecimalString | null;
  standalone: {
    key: string;
    symbol: string;
    name: string;
    weight_pct: DecimalString;
    impact: DecimalString;
    impact_on_total_pct: DecimalString;
  }[];
  excluded_symbols: string[];
}
