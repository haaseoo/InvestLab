"use client";

import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw, TriangleAlert } from "lucide-react";

import { DemoBadge } from "@/components/card";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import type { Portfolio } from "@/types/portfolio";

/** 데이터 출처, 기준 시점, 조회 시각. 데이터를 보여 주는 모든 화면 상단에 둔다. */
export function DataProvenanceBar({
  portfolio,
  isFetching,
}: {
  portfolio: Portfolio;
  isFetching: boolean;
}) {
  const queryClient = useQueryClient();
  const fx = portfolio.fx_rates[0];

  return (
    <div className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-subtle">
        {portfolio.is_demo ? (
          <DemoBadge label="DEMO · 가상 데이터" />
        ) : (
          <span className="font-semibold text-foreground">LIVE · 실제 계좌</span>
        )}
        <span className="num">기준 {formatDateTime(portfolio.as_of)}</span>
        <span className="num">조회 {formatDateTime(portfolio.retrieved_at)}</span>
        {fx && (
          <span className="num">
            환율 {fx.base_currency}/{fx.quote_currency} {Number(fx.rate).toLocaleString("ko-KR")}
          </span>
        )}
        <Button
          variant="ghost"
          onClick={() => queryClient.invalidateQueries()}
          disabled={isFetching}
          className="-mx-2 ml-auto h-9 rounded-full px-3 text-[13px] text-subtle"
        >
          <RefreshCw className={isFetching ? "animate-spin" : ""} aria-hidden="true" />
          데이터 갱신
        </Button>
      </div>

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

export function Assumptions({ items }: { items: string[] }) {
  return (
    <section className="mt-6 px-1">
      <h2 className="mb-2 text-[13px] font-semibold text-subtle">계산 전제</h2>
      <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-subtle">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
