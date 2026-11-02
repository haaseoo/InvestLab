"use client";

import { useQuery } from "@tanstack/react-query";

import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";

/** queryKey에 source가 들어가므로 모드를 바꿔도 다른 모드의 데이터가 재사용되지 않는다. */
export function usePortfolio() {
  const { source } = useSource();
  return useQuery({
    queryKey: ["portfolio", source],
    queryFn: ({ signal }) => api.portfolio(source, signal),
  });
}

export function useHistory() {
  const { source } = useSource();
  return useQuery({
    queryKey: ["history", source],
    queryFn: ({ signal }) => api.history(source, signal),
  });
}

export function useProvidersStatus() {
  return useQuery({
    queryKey: ["providers-status"],
    queryFn: ({ signal }) => api.providersStatus(signal),
  });
}
