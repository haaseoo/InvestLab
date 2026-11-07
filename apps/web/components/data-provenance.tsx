"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, RefreshCw, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useState } from "react";

import { DemoBadge } from "@/components/card";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Portfolio } from "@/types/portfolio";

/**
 * 데이터 출처와 기준 시점. 데이터를 보여 주는 모든 화면 상단에 한 줄로 둔다.
 * 조회 시각과 환율은 "자세히"를 눌러야 보인다.
 */
export function DataProvenanceBar({
  portfolio,
  isFetching,
}: {
  portfolio: Portfolio;
  isFetching: boolean;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const fx = portfolio.fx_rates[0];

  return (
    <div className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[13px] text-subtle">
        {portfolio.is_demo ? (
          <>
            <DemoBadge label="체험용 가상 데이터" />
            <Link href="/settings" className="font-medium underline-offset-2 hover:underline">
              실제 계좌 연결
            </Link>
          </>
        ) : (
          <span className="font-semibold text-foreground">실제 계좌</span>
        )}
        <span className="num">{formatDateTime(portfolio.as_of)} 기준</span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="inline-flex h-9 items-center gap-0.5 rounded-full px-2 hover:text-foreground"
        >
          자세히
          <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
        </button>
        <button
          type="button"
          onClick={() => queryClient.invalidateQueries()}
          disabled={isFetching}
          aria-label="데이터 갱신"
          title="데이터 갱신"
          className="ml-auto grid size-9 place-items-center rounded-full hover:bg-secondary hover:text-foreground disabled:opacity-50"
        >
          <RefreshCw className={cn("size-4", isFetching && "animate-spin")} aria-hidden="true" />
        </button>
      </div>

      {open && (
        <dl className="flex flex-wrap gap-x-5 gap-y-1 rounded-xl bg-secondary/60 px-4 py-3 text-[13px] text-subtle">
          <div className="flex gap-1.5">
            <dt>조회 시각</dt>
            <dd className="num text-foreground">{formatDateTime(portfolio.retrieved_at)}</dd>
          </div>
          {fx && (
            <div className="flex gap-1.5">
              <dt>
                환율 {fx.base_currency}/{fx.quote_currency}
              </dt>
              <dd className="num text-foreground">{Number(fx.rate).toLocaleString("ko-KR")}</dd>
            </div>
          )}
        </dl>
      )}

      {!portfolio.summary.is_complete && (
        <p
          role="status"
          className="flex items-start gap-2 rounded-xl bg-coral-soft px-4 py-3 text-sm text-coral-strong"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          평가금액을 알 수 없어 합계와 비중에서 제외된 종목이 있습니다:{" "}
          {portfolio.summary.unvalued_symbols.join(", ")}
        </p>
      )}
    </div>
  );
}

/** 계산 전제. 기본은 접어 두고 필요할 때 펼쳐 본다. */
export function Assumptions({ items, children }: { items: string[]; children?: ReactNode }) {
  return (
    <details className="group mt-6 px-1">
      <summary className="inline-flex h-9 cursor-pointer list-none items-center gap-1 text-[13px] font-semibold text-subtle hover:text-foreground [&::-webkit-details-marker]:hidden">
        계산 기준 보기
        <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" />
      </summary>
      <ul className="mt-1 list-disc space-y-1 pl-4 text-xs leading-relaxed text-subtle">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {children}
    </details>
  );
}
