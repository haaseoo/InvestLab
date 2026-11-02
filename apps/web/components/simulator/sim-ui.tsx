"use client";

import { CircleAlert, FlaskConical } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("flex min-w-0 flex-col gap-1.5 text-sm", className)}>
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-subtle">{hint}</span>}
    </label>
  );
}

/** 금액·수량 입력. 정밀도를 지키기 위해 문자열 그대로 서버에 보낸다. */
export function DecimalInput({
  value,
  onChange,
  placeholder,
  suffix,
  ariaLabel,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  suffix?: string;
  ariaLabel?: string;
  disabled?: boolean;
}) {
  return (
    <div className="relative">
      <Input
        type="text"
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/[^0-9.\-]/g, ""))}
        placeholder={placeholder}
        aria-label={ariaLabel}
        disabled={disabled}
        className={cn("h-11 rounded-xl text-base num md:text-sm", suffix && "pr-12")}
      />
      {suffix && (
        <span className="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2 text-xs text-subtle">
          {suffix}
        </span>
      )}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: readonly (readonly [T, string])[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-full bg-secondary p-1">
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={cn(
            "h-9 rounded-full px-3.5 text-[13px] font-semibold transition-colors",
            value === v ? "bg-card shadow-sm" : "text-subtle hover:text-foreground",
          )}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

export function SubmitButton({ pending, children }: { pending: boolean; children: ReactNode }) {
  return (
    <Button type="submit" disabled={pending} className="h-11 rounded-full px-6 text-sm">
      <FlaskConical aria-hidden="true" />
      {pending ? "계산 중…" : children}
    </Button>
  );
}

export function SimulationError({ error }: { error: Error | null }) {
  if (!error) return null;
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl bg-coral-soft px-4 py-3 text-sm text-coral-strong"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div>
        <p className="font-medium">{error.message}</p>
        {apiError?.reasons.map((reason) => (
          <p key={reason} className="text-[13px]">
            {reason}
          </p>
        ))}
        {apiError && <p className="mt-0.5 text-xs num opacity-80">오류 코드 {apiError.code}</p>}
      </div>
    </div>
  );
}

export function TheoreticalBadge() {
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-secondary px-2.5 text-xs font-medium text-subtle">
      이론적 시뮬레이션
    </span>
  );
}

export function AssumptionList({
  items,
  title = "계산 전제",
}: {
  items: string[];
  title?: string;
}) {
  return (
    <section className="rounded-xl bg-secondary/60 p-4">
      <h4 className="mb-2 text-[13px] font-semibold">{title}</h4>
      <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-subtle">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export function ResultTable({
  caption,
  head,
  children,
  minWidth = 560,
}: {
  caption: string;
  head: { label: string; numeric?: boolean }[];
  children: ReactNode;
  minWidth?: number;
}) {
  return (
    <div className="relative overflow-x-auto rounded-xl border">
      <table className="w-full text-sm whitespace-nowrap" style={{ minWidth }}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b bg-secondary/50 text-[13px] text-subtle">
            {head.map(({ label, numeric }) => (
              <th
                key={label}
                scope="col"
                className={cn("px-3.5 py-2.5 font-medium", numeric ? "text-right" : "text-left")}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_td]:px-3.5 [&_td]:py-2.5 [&_th]:px-3.5 [&_th]:py-2.5 [&_tr]:border-b [&_tr:last-child]:border-0">
          {children}
        </tbody>
      </table>
    </div>
  );
}
