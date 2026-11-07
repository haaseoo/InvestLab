"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/navigation";

function useActive() {
  const pathname = usePathname();
  return (href: string) => pathname === href || pathname.startsWith(`${href}/`);
}

export function AppSidebar() {
  const isActive = useActive();
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r bg-card px-4 py-6 md:flex">
      <Link href="/dashboard" className="flex items-center gap-2.5 rounded-lg px-3">
        <svg viewBox="0 0 32 32" className="size-8" aria-hidden="true">
          <rect width="32" height="32" rx="9" fill="var(--primary)" />
          <path
            d="M9 21l5-6 4 3 5-7"
            fill="none"
            stroke="var(--coral)"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="text-lg font-bold tracking-tight">InvestLab</span>
      </Link>

      <nav aria-label="주요 메뉴" className="mt-9 flex flex-col gap-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex h-11 items-center gap-3 rounded-xl px-3 text-[15px] font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-subtle hover:bg-secondary hover:text-foreground",
              )}
            >
              <Icon className="size-[18px]" aria-hidden="true" />
              {label}
            </Link>
          );
        })}
      </nav>

      <p className="mt-auto px-3 text-xs leading-relaxed break-keep text-subtle">
        조회 전용 서비스입니다. 매수·매도 주문 기능은 없으며 투자 자문이 아닙니다.
      </p>
    </aside>
  );
}

export function MobileNav() {
  const isActive = useActive();
  return (
    <nav
      aria-label="주요 메뉴"
      className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t bg-card pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = isActive(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex min-h-14 flex-col items-center justify-center gap-1 text-[11.5px] font-medium tracking-tight",
              active ? "text-foreground" : "text-subtle",
            )}
          >
            <Icon className="size-5" strokeWidth={active ? 2.4 : 1.8} aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
