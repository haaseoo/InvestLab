"use client";

import { useQuery } from "@tanstack/react-query";

import { useUserId } from "@/components/auth-provider";
import { api } from "@/lib/api";

/** 사용자 데이터 쿼리는 키에 사용자 id를 넣어 다른 계정의 캐시와 섞이지 않게 한다. */
export function useMe() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["me", userId],
    queryFn: ({ signal }) => api.me(signal),
    enabled: userId !== null,
  });
}

export function useUserSettings() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["user-settings", userId],
    queryFn: ({ signal }) => api.getSettings(signal),
    enabled: userId !== null,
  });
}

export function useSnapshots() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["snapshots", userId],
    queryFn: ({ signal }) => api.snapshots(signal),
    enabled: userId !== null,
  });
}

export function useSimulationHistory() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["simulation-history", userId],
    queryFn: ({ signal }) => api.simulationHistory(signal),
    enabled: userId !== null,
  });
}

export function useKisCredentials() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["kis-credentials", userId],
    queryFn: ({ signal }) => api.kisCredentials(signal),
    enabled: userId !== null,
  });
}
