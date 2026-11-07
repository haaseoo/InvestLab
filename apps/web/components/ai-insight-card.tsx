"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/card";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import type { Insight } from "@/types/analysis";

interface AIInsightCardProps {
  insights: Insight[] | undefined;
  isLoading: boolean;
  isError: boolean;
  /** 처음에 보여 줄 개수. 나머지는 "더 보기"로 펼친다. 없으면 전부 */
  limit?: number;
  className?: string;
}

/**
 * 포트폴리오 인사이트. 지금 보이는 문장은 분석 엔진이 계산한 수치를 옮긴 것이며 AI가 만든
 * 것이 아니다. AI 해석은 OpenAI 연동(Phase 5) 후 같은 카드에 추가한다.
 */
export function AIInsightCard({
  insights,
  isLoading,
  isError,
  limit,
  className,
}: AIInsightCardProps) {
  const [expanded, setExpanded] = useState(false);
  const items = limit && !expanded ? insights?.slice(0, limit) : insights;
  const hidden = (insights?.length ?? 0) - (items?.length ?? 0);

  return (
    <Card title="포트폴리오 인사이트" className={className}>
      {isLoading && (
        <div className="space-y-3" role="status" aria-label="인사이트를 불러오는 중">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-12 rounded-xl" />
          ))}
        </div>
      )}
      {isError && <EmptyState title="인사이트를 불러오지 못했습니다" className="flex-1 py-6" />}
      {items && items.length === 0 && (
        <EmptyState title="표시할 인사이트가 없습니다" className="flex-1 py-6" />
      )}
      {items && items.length > 0 && (
        <ul className="divide-y">
          {items.map((insight) => (
            <li key={insight.key} className="py-3 first:pt-0">
              <p className="text-[15px] font-semibold num">{insight.title}</p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-subtle">{insight.detail}</p>
            </li>
          ))}
        </ul>
      )}

      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-1 inline-flex h-9 items-center gap-1 self-start text-[13px] font-medium text-subtle hover:text-foreground"
        >
          {hidden}개 더 보기
          <ChevronDown className="size-3.5" aria-hidden="true" />
        </button>
      )}
      <p className="mt-auto pt-4 text-xs leading-relaxed text-subtle">
        계산된 수치를 문장으로 옮긴 것이며 투자 권유가 아닙니다. AI 해석은 준비 중입니다.
      </p>
    </Card>
  );
}
