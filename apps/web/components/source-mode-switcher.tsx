"use client";

import { useSource } from "@/hooks/use-source";
import { cn } from "@/lib/utils";
import type { Source } from "@/types/portfolio";

const OPTIONS: { value: Source; label: string }[] = [
  { value: "mock", label: "MOCK" },
  { value: "live", label: "LIVE" },
];

export function SourceModeSwitcher() {
  const { source, setSource } = useSource();
  const select = (next: Source) => {
    if (next !== source) setSource(next);
  };

  return (
    <div
      role="group"
      aria-label="데이터 모드"
      className="inline-flex rounded-full border bg-secondary p-1"
    >
      {OPTIONS.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          aria-pressed={source === value}
          onClick={() => select(value)}
          className={cn(
            "h-9 min-w-16 rounded-full px-3.5 text-[13px] font-semibold tracking-wide transition-colors",
            source === value
              ? "bg-primary text-primary-foreground"
              : "text-subtle hover:text-foreground",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
