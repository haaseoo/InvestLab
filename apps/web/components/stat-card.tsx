import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: LucideIcon;
  className?: string;
}

export function StatCard({ label, value, hint, icon: Icon, className }: StatCardProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2.5 card-surface p-4 md:p-5", className)}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-subtle md:text-[15px]">{label}</h3>
        {Icon && (
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-secondary">
            <Icon className="size-4 text-faint" aria-hidden="true" />
          </span>
        )}
      </div>
      <div className="text-[17px] leading-tight font-bold num tracking-tight break-keep md:text-[20px] xl:text-[22px] [&_.num]:whitespace-normal">
        {value}
      </div>
      {hint && <div className="text-xs text-subtle md:text-[13px]">{hint}</div>}
    </div>
  );
}
