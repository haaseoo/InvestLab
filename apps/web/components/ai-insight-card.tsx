import { ArrowRight, Calculator, Sparkles } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/card";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Insight } from "@/types/analysis";

interface AIInsightCardProps {
  insights: Insight[] | undefined;
  isLoading: boolean;
  isError: boolean;
  /** 표시할 최대 개수. 없으면 전부 */
  limit?: number;
  showLink?: boolean;
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
  showLink = false,
  className,
}: AIInsightCardProps) {
  const items = limit ? insights?.slice(0, limit) : insights;

  return (
    <Card
      title="포트폴리오 인사이트"
      action={
        <span className="inline-flex h-6 items-center gap-1 rounded-full bg-secondary px-2.5 text-xs font-medium text-subtle">
          <Calculator className="size-3" aria-hidden="true" />
          분석 엔진 계산
        </span>
      }
      className={className}
    >
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

      <div className={cn("mt-auto space-y-3 pt-4")}>
        {showLink && insights && limit && insights.length > limit && (
          <Link
            href="/analytics"
            className="inline-flex h-9 items-center gap-1 text-[13px] font-medium text-subtle hover:text-foreground"
          >
            인사이트 {insights.length}개 모두 보기
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        )}
        <div className="flex items-start gap-2.5 rounded-xl bg-secondary/70 px-3.5 py-3 text-[13px]">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden="true" />
          <p className="text-subtle">
            <span className="font-semibold text-foreground">AI 해석 준비 중</span> · OpenAI가
            연결되지 않아 AI 분석은 실행하지 않았습니다. 위 문장은 계산된 수치를 그대로 옮긴 것이며
            투자 권유가 아닙니다.
          </p>
        </div>
      </div>
    </Card>
  );
}
