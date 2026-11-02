"use client";

import { Check, LogIn, Minus } from "lucide-react";
import Link from "next/link";

import { ErrorState } from "@/components/state";
import { useProvidersStatus } from "@/hooks/use-portfolio";
import { useSource } from "@/hooks/use-source";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProviderStatus } from "@/types/portfolio";

export function ProviderChecklist({ checks }: { checks: ProviderStatus["checks"] }) {
  return (
    <ul className="w-full max-w-sm space-y-2 text-left text-sm">
      {checks.map(({ key, label, ok }) => (
        <li key={key} className="flex items-center gap-2.5">
          <span
            className={cn(
              "grid size-5 shrink-0 place-items-center rounded-full",
              ok ? "bg-primary text-primary-foreground" : "bg-secondary text-subtle",
            )}
          >
            {ok ? (
              <Check className="size-3" aria-hidden="true" />
            ) : (
              <Minus className="size-3" aria-hidden="true" />
            )}
          </span>
          <span className={ok ? "" : "text-subtle"}>{label}</span>
          <span className="ml-auto shrink-0 text-xs text-subtle">{ok ? "완료" : "미완료"}</span>
        </li>
      ))}
    </ul>
  );
}

const LIVE_ERROR_TITLES: Record<string, string> = {
  AUTH_REQUIRED: "LIVE 데이터는 로그인이 필요합니다",
  INVALID_TOKEN: "로그인이 만료되었습니다",
  LIVE_FORBIDDEN: "이 계정은 LIVE 조회 권한이 없습니다",
  AUTH_NOT_CONFIGURED: "사용자 인증이 구성되지 않았습니다",
  LIVE_OWNER_NOT_CONFIGURED: "LIVE 계좌 소유자가 지정되지 않았습니다",
  KIS_NOT_CONFIGURED: "실제 계좌가 연결되어 있지 않습니다",
  KIS_AUTH_FAILED: "한국투자증권 인증에 실패했습니다",
  KIS_RATE_LIMITED: "한국투자증권 호출 한도에 걸렸습니다",
  KIS_UNAVAILABLE: "한국투자증권 서버에 연결하지 못했습니다",
  KIS_API_ERROR: "한국투자증권이 오류를 반환했습니다",
  KIS_RESPONSE_INVALID: "한국투자증권 응답을 해석하지 못했습니다",
  DB_NOT_CONFIGURED: "실제 계좌 이력 저장소가 연결되지 않았습니다",
  DB_UNAVAILABLE: "실제 계좌 이력 저장소에 연결하지 못했습니다",
};

/** 데이터 조회 실패 화면. LIVE 실패 시 어떤 데이터도 대신 보여 주지 않는다. */
export function QueryError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const { source } = useSource();
  const status = useProvidersStatus();
  const apiError = error instanceof ApiError ? error : null;

  if (apiError?.status === 0) {
    return (
      <ErrorState
        title="API 서버에 연결할 수 없습니다"
        description="FastAPI 서버가 실행 중인지 확인해 주세요. 서버에 연결되기 전에는 어떤 데이터도 표시하지 않습니다."
        code={apiError.code}
        onRetry={onRetry}
      />
    );
  }

  if (source === "live") {
    const live = status.data?.providers.find((p) => p.source === "live");
    const code = apiError?.code ?? "";
    const needsLogin = code === "AUTH_REQUIRED" || code === "INVALID_TOKEN";
    const title = LIVE_ERROR_TITLES[code] ?? "실제 계좌 데이터를 불러오지 못했습니다";
    return (
      <ErrorState
        title={title}
        description={`${apiError?.message ?? "LIVE 데이터를 조회하지 못했습니다."} 가상 데이터로 대체하지 않습니다. 시연 데이터를 보려면 상단에서 MOCK을 선택하세요.`}
        code={apiError?.code}
        onRetry={needsLogin ? undefined : onRetry}
      >
        {needsLogin && (
          <Link
            href="/login"
            className="inline-flex h-11 items-center gap-1.5 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground hover:bg-primary/85"
          >
            <LogIn className="size-4" aria-hidden="true" />
            로그인
          </Link>
        )}
        {live && live.checks.length > 0 && (
          <div className="w-full max-w-sm rounded-xl bg-secondary/60 p-4">
            <h3 className="mb-3 text-left text-sm font-semibold">LIVE 연결 준비 상태</h3>
            <ProviderChecklist checks={live.checks} />
          </div>
        )}
      </ErrorState>
    );
  }

  return (
    <ErrorState
      title="데이터를 불러오지 못했습니다"
      description={apiError?.message ?? error.message}
      code={apiError?.code}
      onRetry={onRetry}
    />
  );
}
