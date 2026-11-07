"use client";

import { LogIn, Settings, UserRound } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

/** 헤더 오른쪽의 계정 메뉴. 설정 화면으로 들어가는 입구이며, 로그아웃은 설정 화면에 있다. */
export function AccountControl() {
  const { configured, ready, session } = useAuth();
  const settingsLink = (
    <Link
      href="/settings"
      aria-label="설정"
      className="grid size-11 place-items-center rounded-full border bg-card text-subtle hover:bg-secondary hover:text-foreground"
    >
      <Settings className="size-4" aria-hidden="true" />
    </Link>
  );

  if (!configured || !ready) return settingsLink;

  if (!session) {
    return (
      <div className="flex items-center gap-2">
        <Link
          href="/login"
          className="inline-flex h-11 items-center gap-1.5 rounded-full border bg-card px-4 text-[13px] font-semibold hover:bg-secondary"
        >
          <LogIn className="size-4" aria-hidden="true" />
          로그인
        </Link>
        {settingsLink}
      </div>
    );
  }

  return (
    <Link
      href="/settings"
      className="inline-flex h-11 max-w-56 items-center gap-1.5 rounded-full border bg-card px-3 text-[13px] font-medium hover:bg-secondary"
      aria-label="계정 및 설정"
    >
      <UserRound className="size-4 shrink-0" aria-hidden="true" />
      <span className="hidden truncate sm:inline">{session.user.email}</span>
      <Settings className="size-4 shrink-0 text-subtle" aria-hidden="true" />
    </Link>
  );
}
