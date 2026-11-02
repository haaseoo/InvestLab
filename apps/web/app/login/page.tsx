"use client";

import { LogIn, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Card } from "@/components/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const { configured, ready, session, signIn, signOut } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError(null);
    const message = await signIn(email.trim(), password);
    setPending(false);
    if (message) {
      setError(message);
      return;
    }
    setPassword("");
    router.replace("/dashboard");
  };

  return (
    <div className="mx-auto max-w-md">
      <Card>
        {!configured ? (
          <p className="text-sm text-subtle">
            로그인 설정(Supabase URL·공개 키)이 없어 로그인할 수 없습니다. Mock 모드는 로그인 없이
            사용할 수 있습니다.
          </p>
        ) : !ready ? (
          <p className="text-sm text-subtle" role="status">
            로그인 상태를 확인하는 중입니다.
          </p>
        ) : session ? (
          <div className="space-y-4">
            <div>
              <p className="text-[13px] text-subtle">로그인한 계정</p>
              <p className="font-semibold break-all">{session.user.email}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href="/dashboard"
                className="inline-flex h-11 items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground hover:bg-primary/85"
              >
                대시보드로 이동
              </Link>
              <Button
                variant="outline"
                onClick={() => signOut()}
                className="h-11 rounded-full px-5"
              >
                <LogOut aria-hidden="true" />
                로그아웃
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold tracking-tight">계정으로 로그인</h2>
              <p className="text-[13px] text-subtle">
                LIVE 데이터와 저장 기능은 로그인 후 사용할 수 있습니다. 신규 가입은 받지 않습니다.
              </p>
            </div>
            <label className="block space-y-1.5 text-sm">
              <span className="font-medium">이메일</span>
              <Input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-11 rounded-xl text-base md:text-sm"
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="font-medium">비밀번호</span>
              <Input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-11 rounded-xl text-base md:text-sm"
              />
            </label>
            {error && (
              <p
                role="alert"
                className="rounded-xl bg-coral-soft px-4 py-3 text-sm text-coral-strong"
              >
                {error}
              </p>
            )}
            <Button type="submit" disabled={pending} className="h-11 w-full rounded-full">
              <LogIn aria-hidden="true" />
              {pending ? "로그인 중…" : "로그인"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
