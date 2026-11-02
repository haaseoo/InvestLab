"use client";

import { Hourglass } from "lucide-react";

import { AssetAllocationChart } from "@/components/asset-allocation-chart";
import { Card } from "@/components/card";
import { Assumptions, DataProvenanceBar } from "@/components/data-provenance";
import { QueryError } from "@/components/query-error";
import { RiskIndicator } from "@/components/risk-indicator";
import { EmptyState } from "@/components/empty-state";
import { LoadingSkeleton } from "@/components/state";
import { usePortfolio } from "@/hooks/use-portfolio";
import { formatKrwCompact } from "@/lib/format";

const PLANNED = [
  "국가별·섹터별 비중",
  "ETF 구성 종목 중복 분석 (실제 편입 종목 데이터 필요)",
  "포트폴리오 위험 지표 (충분한 이력 데이터 필요)",
];

export default function AnalyticsPage() {
  const portfolio = usePortfolio();

  if (portfolio.isPending) return <LoadingSkeleton />;
  if (portfolio.isError) {
    return <QueryError error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  }

  const { data } = portfolio;
  const { summary, concentration } = data;

  return (
    <div>
      <DataProvenanceBar portfolio={data} isFetching={portfolio.isFetching} />
      <div className="grid gap-3 md:gap-4 lg:grid-cols-2">
        <Card title="종목 집중도">
          <div className="space-y-5">
            <RiskIndicator
              label="최대 보유 종목"
              valuePct={concentration.top1_pct}
              description="평가금액이 가장 큰 1개 종목의 비중"
            />
            <RiskIndicator
              label="상위 3개 종목"
              valuePct={concentration.top3_pct}
              description="평가금액 상위 3개 종목의 비중 합"
            />
            <RiskIndicator
              label="상위 5개 종목"
              valuePct={concentration.top5_pct}
              description="평가금액 상위 5개 종목의 비중 합"
            />
          </div>
          <p className="mt-5 text-xs leading-relaxed text-subtle">
            보유 종목 단위의 비중입니다. ETF 내부 편입 종목을 펼쳐 계산한 실제 노출도가 아닙니다.
          </p>
        </Card>

        <Card title="자산군별 비중">
          {data.allocation.length > 0 ? (
            <AssetAllocationChart
              slices={data.allocation}
              currency={summary.valuation_currency}
              centerLabel="총 평가자산"
              centerValue={
                summary.total_market_value === null
                  ? "–"
                  : `${formatKrwCompact(Number(summary.total_market_value))}원`
              }
            />
          ) : (
            <EmptyState title="표시할 자산이 없습니다" className="flex-1" />
          )}
        </Card>

        <Card title="다음 단계에서 추가되는 분석" className="lg:col-span-2">
          <EmptyState
            icon={Hourglass}
            title="아직 제공하지 않는 분석입니다"
            description="데이터나 계산이 준비되지 않은 항목은 수치를 임의로 만들지 않습니다."
            className="py-4"
          >
            <ul className="mt-1 space-y-1 text-sm text-subtle">
              {PLANNED.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </EmptyState>
        </Card>
      </div>
      <Assumptions items={data.assumptions} />
    </div>
  );
}
