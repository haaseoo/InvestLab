"use client";

import { usePathname } from "next/navigation";

import { AccountControl } from "@/components/layout/account-control";
import { SourceModeSwitcher } from "@/components/source-mode-switcher";
import { NAV_ITEMS } from "@/lib/navigation";

export function AppHeader() {
  const pathname = usePathname();
  const item = NAV_ITEMS.find(({ href }) => pathname === href || pathname.startsWith(`${href}/`));

  return (
    <header className="mx-auto flex w-full max-w-[1240px] flex-wrap items-center justify-between gap-3 px-4 pt-5 pb-5 md:px-8 md:pt-8 md:pb-6">
      <h1 className="text-2xl font-bold tracking-tight md:text-[28px]">
        {item?.title ?? (pathname === "/login" ? "로그인" : "InvestLab")}
      </h1>
      <div className="flex items-center gap-2">
        <SourceModeSwitcher />
        <AccountControl />
      </div>
    </header>
  );
}
