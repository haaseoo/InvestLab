"use client";

import { LogIn, LogOut, UserRound } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

/** 헤더의 로그인 상태 표시. 로그인 설정이 없으면 아무것도 그리지 않는다. */
export function AccountControl() {
  const { configured, ready, session, signOut } = useAuth();
  if (!configured || !ready) return null;

  if (!session) {
    return (
      <Link
        href="/login"
        className="inline-flex h-11 items-center gap-1.5 rounded-full border bg-card px-4 text-[13px] font-semibold hover:bg-secondary"
      >
        <LogIn className="size-4" aria-hidden="true" />
        로그인
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <Link
        href="/settings"
        className="inline-flex h-11 max-w-48 items-center gap-1.5 rounded-full border bg-card px-3 text-[13px] font-medium hover:bg-secondary"
        aria-label="계정 설정"
      >
        <UserRound className="size-4 shrink-0" aria-hidden="true" />
        <span className="hidden truncate sm:inline">{session.user.email}</span>
      </Link>
      <button
        type="button"
        onClick={() => signOut()}
        aria-label="로그아웃"
        className="grid size-11 place-items-center rounded-full text-subtle hover:bg-secondary hover:text-foreground"
      >
        <LogOut className="size-4" aria-hidden="true" />
      </button>
    </div>
  );
}
