import type { ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar, MobileNav } from "@/components/layout/app-sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col pb-20 md:pb-0">
        <AppHeader />
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-4 pb-10 md:px-8">{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
