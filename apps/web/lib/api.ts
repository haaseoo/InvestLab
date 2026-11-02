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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, cache: "no-store" });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("API 서버에 연결할 수 없습니다.", 0, "NETWORK_ERROR");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.error?.message ?? "요청을 처리하지 못했습니다.",
      response.status,
      body?.error?.code ?? "UNKNOWN_ERROR",
      body?.error?.details?.reasons ?? [],
    );
  }
  return response.json();
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  portfolio: (source: Source, signal?: AbortSignal) =>
    request<Portfolio>(`/api/v1/portfolio?source=${source}`, { signal }),
  history: (source: Source, signal?: AbortSignal) =>
    request<History>(`/api/v1/portfolio/history?source=${source}`, { signal }),
  risk: (source: Source, signal?: AbortSignal) =>
    request<Risk>(`/api/v1/analytics/risk?source=${source}`, { signal }),
  providersStatus: (signal?: AbortSignal) =>
    request<ProvidersStatus>("/api/v1/providers/status", { signal }),
  simulateBuy: (source: Source, body: BuyRequest) =>
    post<BuyResult>(`/api/v1/simulations/buy?source=${source}`, body),
  simulateRebalance: (source: Source, body: RebalanceRequest) =>
    post<RebalanceResult>(`/api/v1/simulations/rebalance?source=${source}`, body),
  simulateScenario: (source: Source, body: ScenarioRequest) =>
    post<ScenarioResult>(`/api/v1/simulations/scenario?source=${source}`, body),
};
