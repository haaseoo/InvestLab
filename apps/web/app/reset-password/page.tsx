"use client";

import { KeyRound } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { Card } from "@/components/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getSupabase } from "@/lib/supabase";

type Stage = "checking" | "ready" | "invalid" | "done";

async function startRecovery(hash: string): Promise<Stage> {
  const params = new URLSearchParams(hash);
  const supabase = getSupabase();
  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");
  if (!supabase || params.get("type") !== "recovery" || !accessToken || !refreshToken) {
    return "invalid";
  }
  try {
    const { error } = await supabase.auth.setSession({
      access_token: accessToken,
      refresh_token: refreshToken,
    });
    return error ? "invalid" : "ready";
  } catch {
    return "invalid";
  }
}

/**
 * Supabase 비밀번호 재설정 메일의 링크가 도착하는 화면.
 * 링크는 주소의 # 뒤에 일회용 세션(type=recovery)을 싣고 온다. 읽은 즉시 주소에서 지운다.
 * 비밀번호는 Supabase Auth로만 보내며 InvestLab 서버를 거치지 않는다.
 */
export default function ResetPasswordPage() {
  const [stage, setStage] = useState<Stage>("checking");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    // 토큰이 주소창·방문 기록에 남지 않게 바로 지운다.
    window.history.replaceState(null, "", window.location.pathname);
    let active = true;
    startRecovery(hash).then((next) => {
      if (active) setStage(next);
    });
    return () => {
      active = false;
    };
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("비밀번호는 8자 이상으로 정해 주세요.");
      return;
    }
    if (password !== confirm) {
      setError("두 비밀번호가 같지 않습니다.");
      return;
    }
    const supabase = getSupabase();
    if (!supabase) return;
    setPending(true);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setPending(false);
    if (updateError) {
      setError(
        /different from the old/i.test(updateError.message)
          ? "이전과 다른 비밀번호를 정해 주세요."
          : /weak|characters/i.test(updateError.message)
            ? "비밀번호가 너무 단순합니다. 더 길거나 복잡하게 정해 주세요."
            : "비밀번호를 바꾸지 못했습니다. 재설정 메일을 다시 받아 시도해 주세요.",
      );
      return;
    }
    setPassword("");
    setConfirm("");
    setStage("done");
  };

  return (
    <div className="mx-auto max-w-md">
      <Card title="새 비밀번호 설정">
        {stage === "checking" && <p className="text-sm text-subtle">링크를 확인하는 중입니다…</p>}
        {stage === "invalid" && (
          <div className="space-y-3 text-sm">
            <p>
              재설정 링크가 없거나 만료되었습니다. 링크는 한 번만 쓸 수 있고 일정 시간이 지나면
              만료됩니다.
            </p>
            <p className="text-subtle">
              Supabase 대시보드 Authentication → Users에서 재설정 메일을 다시 보낸 뒤, 새 메일의
              링크를 눌러 주세요.
            </p>
          </div>
        )}
        {stage === "done" && (
          <div className="space-y-4 text-sm">
            <p>비밀번호를 바꿨습니다. 지금 로그인된 상태입니다.</p>
            <Link
              href="/dashboard"
              className="inline-flex h-11 items-center rounded-full bg-primary px-5 font-medium text-primary-foreground hover:bg-primary/85"
            >
              대시보드로 이동
            </Link>
          </div>
        )}
        {stage === "ready" && (
          <form onSubmit={submit} className="space-y-4">
            <label className="block space-y-1.5 text-sm">
              <span className="font-medium">새 비밀번호</span>
              <Input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-11"
                required
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="font-medium">새 비밀번호 확인</span>
              <Input
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="h-11"
                required
              />
            </label>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" disabled={pending} className="h-11 w-full rounded-full">
              <KeyRound aria-hidden="true" />
              {pending ? "저장 중…" : "비밀번호 저장"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
