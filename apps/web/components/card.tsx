import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface CardProps {
  title?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** 모든 화면이 공유하는 카드 틀. 제목은 h2로 렌더링한다. */
export function Card({ title, action, className, children }: CardProps) {
  return (
    <section className={cn("flex min-w-0 flex-col card-surface p-5 md:p-6", className)}>
      {(title || action) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-lg font-semibold tracking-tight">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function DemoBadge({ label = "DEMO" }: { label?: string }) {
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-coral-soft px-2.5 text-xs font-semibold text-coral-strong">
      {label}
    </span>
  );
}
