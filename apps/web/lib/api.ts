import { getAccessToken } from "@/lib/supabase";
import type {
  BuyRequest,
  BuyResult,
  RebalanceRequest,
  RebalanceResult,
  Risk,
  ScenarioRequest,
  ScenarioResult,
} from "@/types/analysis";
import type { History, Portfolio, ProvidersStatus, Source } from "@/types/portfolio";
import type {
  KisCredentialsInput,
  KisCredentialsStatus,
  Me,
  SimulationHistory,
  SimulationHistoryCreate,
  SimulationHistoryItem,
  SnapshotDetail,
  SnapshotList,
  UserSettings,
} from "@/types/user";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    /** 0은 서버에 도달하지 못한 경우다. */
    readonly status: number,
    readonly code: string,
    /** 입력 검증 실패 사유. 서버가 준 문구 그대로다. */
    readonly reasons: string[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface Options {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** 로그인 토큰을 보낼지. LIVE 데이터와 사용자 데이터 요청에만 보낸다. */
  auth?: boolean;
}

async function request<T>(path: string, { method = "GET", body, signal, auth }: Options = {}) {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = await getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("API 서버에 연결할 수 없습니다.", 0, "NETWORK_ERROR");
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(
      payload?.error?.message ?? "요청을 처리하지 못했습니다.",
      response.status,
      payload?.error?.code ?? "UNKNOWN_ERROR",
      payload?.error?.details?.reasons ?? [],
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const live = (source: Source) => source === "live";

export const api = {
  portfolio: (source: Source, signal?: AbortSignal) =>
    request<Portfolio>(`/api/v1/portfolio?source=${source}`, { signal, auth: live(source) }),
  history: (source: Source, signal?: AbortSignal) =>
    request<History>(`/api/v1/portfolio/history?source=${source}`, {
      signal,
      auth: live(source),
    }),
  risk: (source: Source, signal?: AbortSignal) =>
    request<Risk>(`/api/v1/analytics/risk?source=${source}`, { signal, auth: live(source) }),
  providersStatus: (signal?: AbortSignal) =>
    request<ProvidersStatus>("/api/v1/providers/status", { signal }),
  simulateBuy: (source: Source, body: BuyRequest) =>
    request<BuyResult>(`/api/v1/simulations/buy?source=${source}`, {
      method: "POST",
      body,
      auth: live(source),
    }),
  simulateRebalance: (source: Source, body: RebalanceRequest) =>
    request<RebalanceResult>(`/api/v1/simulations/rebalance?source=${source}`, {
      method: "POST",
      body,
      auth: live(source),
    }),
  simulateScenario: (source: Source, body: ScenarioRequest) =>
    request<ScenarioResult>(`/api/v1/simulations/scenario?source=${source}`, {
      method: "POST",
      body,
      auth: live(source),
    }),

  // 로그인 사용자 데이터
  me: (signal?: AbortSignal) => request<Me>("/api/v1/me", { signal, auth: true }),
  getSettings: (signal?: AbortSignal) =>
    request<UserSettings>("/api/v1/settings", { signal, auth: true }),
  putSettings: (body: Omit<UserSettings, "updated_at">) =>
    request<UserSettings>("/api/v1/settings", { method: "PUT", body, auth: true }),
  snapshots: (signal?: AbortSignal) =>
    request<SnapshotList>("/api/v1/snapshots", { signal, auth: true }),
  captureSnapshot: () =>
    request<SnapshotDetail>("/api/v1/snapshots?source=live", { method: "POST", auth: true }),
  deleteSnapshot: (id: string) =>
    request<void>(`/api/v1/snapshots/${encodeURIComponent(id)}`, {
      method: "DELETE",
      auth: true,
    }),
  simulationHistory: (signal?: AbortSignal) =>
    request<SimulationHistory>("/api/v1/simulations/history", { signal, auth: true }),
  saveSimulation: (body: SimulationHistoryCreate) =>
    request<SimulationHistoryItem>("/api/v1/simulations/history", {
      method: "POST",
      body,
      auth: true,
    }),
  kisCredentials: (signal?: AbortSignal) =>
    request<KisCredentialsStatus>("/api/v1/kis/credentials", { signal, auth: true }),
  putKisCredentials: (body: KisCredentialsInput) =>
    request<KisCredentialsStatus>("/api/v1/kis/credentials", {
      method: "PUT",
      body,
      auth: true,
    }),
  deleteKisCredentials: () =>
    request<void>("/api/v1/kis/credentials", { method: "DELETE", auth: true }),
  deleteSimulation: (id: string) =>
    request<void>(`/api/v1/simulations/history/${encodeURIComponent(id)}`, {
      method: "DELETE",
      auth: true,
    }),
};
