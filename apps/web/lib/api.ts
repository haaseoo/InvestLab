import type { History, Portfolio, ProvidersStatus, Source } from "@/types/portfolio";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    /** 0은 서버에 도달하지 못한 경우다. */
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { signal, cache: "no-store" });
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
    );
  }
  return response.json();
}

export const api = {
  portfolio: (source: Source, signal?: AbortSignal) =>
    request<Portfolio>(`/api/v1/portfolio?source=${source}`, signal),
  history: (source: Source, signal?: AbortSignal) =>
    request<History>(`/api/v1/portfolio/history?source=${source}`, signal),
  providersStatus: (signal?: AbortSignal) =>
    request<ProvidersStatus>("/api/v1/providers/status", signal),
};
