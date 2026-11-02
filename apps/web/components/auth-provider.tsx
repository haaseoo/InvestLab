"use client";

import type { Session } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect, useRef, useState } from "react";

import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";
import { authConfigured, getSupabase } from "@/lib/supabase";

interface AuthState {
  configured: boolean;
  /** 저장된 세션 확인이 끝났는지 */
  ready: boolean;
  session: Session | null;
  signIn: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function describeError(message: string, status?: number): string {
  if (status === 429) return "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.";
  if (/invalid login credentials/i.test(message))
    return "이메일 또는 비밀번호가 올바르지 않습니다.";
  if (/email not confirmed/i.test(message)) return "이메일 인증이 끝나지 않은 계정입니다.";
  if (/fetch|network/i.test(message)) return "인증 서버에 연결할 수 없습니다.";
  return "로그인하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { setSource } = useSource();
  const [state, setState] = useState<{ ready: boolean; session: Session | null }>({
    ready: !authConfigured,
    session: null,
  });
  const lastUserId = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    // 비밀번호 재설정 메일 링크는 Site URL(첫 화면)로 온다. 재설정 화면으로 # 부분을 그대로 넘긴다.
    const { hash, pathname } = window.location;
    if (hash.includes("type=recovery") && pathname !== "/reset-password") {
      window.location.replace(`/reset-password${hash}`);
      return;
    }
    const supabase = getSupabase();
    if (!supabase) return;
    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      setState({ ready: true, session });
      const userId = session?.user.id ?? null;
      // 사용자가 바뀌면(로그인·로그아웃) 이전 사용자의 응답이 남지 않게 모든 쿼리를 초기화한다.
      if (lastUserId.current !== undefined && lastUserId.current !== userId) {
        queryClient.resetQueries();
      }
      lastUserId.current = userId;
      // 방금 로그인했다면 저장된 기본 데이터 모드를 적용한다.
      if (event === "SIGNED_IN" && session) {
        api
          .getSettings()
          .then((settings) => setSource(settings.preferred_source))
          .catch(() => undefined);
      }
    });
    return () => data.subscription.unsubscribe();
  }, [queryClient, setSource]);

  const value: AuthState = {
    configured: authConfigured,
    ready: state.ready,
    session: state.session,
    signIn: async (email, password) => {
      const supabase = getSupabase();
      if (!supabase) return "로그인 설정이 되어 있지 않습니다.";
      try {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        return error ? describeError(error.message, error.status) : null;
      } catch (error) {
        return describeError(error instanceof Error ? error.message : "");
      }
    },
    signOut: async () => {
      await getSupabase()?.auth.signOut();
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider가 필요합니다.");
  return context;
}

export function useUserId(): string | null {
  return useAuth().session?.user.id ?? null;
}
