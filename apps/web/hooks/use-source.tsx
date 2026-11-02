"use client";

import { useCallback, useSyncExternalStore } from "react";

import type { Source } from "@/types/portfolio";

const STORAGE_KEY = "investlab.source";
const listeners = new Set<() => void>();

function read(): Source {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "live" ? "live" : "mock";
  } catch {
    return "mock";
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** 화면에서 선택한 데이터 모드. 선택일 뿐 권한이 아니며, LIVE 인가는 서버가 판단한다. */
export function useSource() {
  const source = useSyncExternalStore<Source>(subscribe, read, () => "mock");

  const setSource = useCallback((next: Source) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // 저장할 수 없는 환경에서는 기본값(mock)을 유지한다.
    }
    listeners.forEach((listener) => listener());
  }, []);

  return { source, setSource };
}
