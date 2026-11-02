"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { useSource } from "@/hooks/use-source";
import { cn } from "@/lib/utils";
import type { Source } from "@/types/portfolio";

const OPTIONS: { value: Source; label: string }[] = [
  { value: "mock", label: "MOCK" },
  { value: "live", label: "LIVE" },
];

export function SourceModeSwitcher() {
  const { source, setSource } = useSource();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const select = (next: Source) => {
    if (next === source) return;
    if (next === "live") setConfirmOpen(true);
    else setSource(next);
  };

  return (
    <>
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
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="LIVE 모드로 전환할까요?"
        description="LIVE 모드는 연결된 실제 계좌만 조회합니다. 연결되어 있지 않거나 오류가 나면 안내 화면을 보여 주며, 가상 데이터로 대체하지 않습니다."
        confirmLabel="LIVE로 전환"
        onConfirm={() => setSource("live")}
      />
    </>
  );
}
