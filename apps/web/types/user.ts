import type { DecimalString, Source } from "@/types/portfolio";

export interface Me {
  user_id: string;
  email: string | null;
  is_live_owner: boolean;
  database_available: boolean;
}

export interface UserSettings {
  theme: "light" | "dark" | "system";
  preferred_currency: string;
  preferred_source: Source;
  mask_account_numbers: boolean;
  updated_at: string | null;
}

export interface SnapshotSummary {
  id: string;
  source: Source;
  valuation_currency: string;
  total_market_value: DecimalString;
  total_cost_basis: DecimalString;
  holding_count: number;
  valued_holding_count: number;
  is_complete: boolean;
  as_of: string;
  captured_at: string;
}

export interface SnapshotDetail extends SnapshotSummary {
  content_hash: string;
}

export interface SnapshotList {
  snapshots: SnapshotSummary[];
}

export type SimulationType = "buy" | "rebalance" | "scenario";

export interface SimulationHistoryCreate {
  simulation_type: SimulationType;
  source: Source;
  input: object;
  result: object;
  as_of?: string | null;
}

export interface SimulationHistoryItem {
  id: string;
  simulation_type: SimulationType;
  source: Source;
  is_demo: boolean;
  input: Record<string, unknown>;
  result: Record<string, unknown>;
  as_of: string | null;
  created_at: string;
}

export interface SimulationHistory {
  items: SimulationHistoryItem[];
}
