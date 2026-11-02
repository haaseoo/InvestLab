"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { ApiError } from "@/lib/api";

function shouldRetry(failureCount: number, error: Error) {
  // 네트워크 오류와 예기치 못한 5xx만 한 번 재시도한다. 인증·설정 오류는 재시도해도 같다.
  if (error instanceof ApiError && error.status !== 0 && error.status !== 500) return false;
  return failureCount < 1;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60_000, refetchOnWindowFocus: false, retry: shouldRetry },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
