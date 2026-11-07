"use client";

import { ArrowRight, Wallet } from "lucide-react";
import Link from "next/link";

import { AIInsightCard } from "@/components/ai-insight-card";
import { AssetAllocationChart } from "@/components/asset-allocation-chart";
import { Card, DemoBadge } from "@/components/card";
import { Assumptions, DataProvenanceBar } from "@/components/data-provenance";
import { EmptyState } from "@/components/empty-state";
import { HoldingValueBars } from "@/components/holding-value-bars";
import { PnlText } from "@/components/pnl-text";
import { PortfolioChart } from "@/components/portfolio-chart";
import { QueryError } from "@/components/query-error";
import { LoadingSkeleton } from "@/components/state";
import { Skeleton } from "@/components/ui/skeleton";
import { useHistory, usePortfolio, useRisk } from "@/hooks/use-portfolio";
import { sectorColor, sectorDonutSlices } from "@/lib/chart";
import {
  directionOf,
  formatKrwCompact,
  formatMoney,
  formatSignedMoney,
  formatSignedPercent,
} from "@/lib/format";
import type { AllocationSlice, History, PortfolioSummary } from "@/types/portfolio";

function pnlWord(value: string | null) {
  const direction = directionOf(value);
  if (direction === "up") return "평가이익";
  if (direction === "down") return "평가손실";
  return direction === "flat" ? "손익 없음" : "계산 불가";
}

/** 총 평가자산과 손익을 한 카드에 모은다. 홈에서 가장 먼저 읽는 숫자다. */
function TotalAssetCard({ summary }: { summary: PortfolioSummary }) {
  const currency = summary.valuation_currency;
  return (
    <section className="card-surface p-5 md:p-6">
      <div className="flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-full bg-secondary">
          <Wallet className="size-4 text-faint" aria-hidden="true" />
        </span>
        <h2 className="text-[15px] font-medium text-subtle">총 평가자산</h2>
      </div>
      <p className="mt-2 text-[28px] leading-tight font-bold num tracking-tight md:text-[34px]">
        {formatMoney(summary.total_market_value, currency)}
      </p>
      <p className="mt-1 text-[15px] num">
        <PnlText
          value={summary.total_unrealized_pnl}
          text={formatSignedMoney(summary.total_unrealized_pnl, currency)}
          className="font-semibold"
        />{" "}
        <PnlText
          value={summary.total_unrealized_pnl_pct}
          text={`(${formatSignedPercent(summary.total_unrealized_pnl_pct)})`}
          className="font-semibold"
        />
        <span className="ml-1.5 text-[13px] text-subtle">
          {pnlWord(summary.total_unrealized_pnl)}
        </span>
      </p>

      <dl className="mt-5 grid grid-cols-2 gap-3 border-t pt-4 text-sm">
        <div>
          <dt className="text-[13px] text-subtle">투자 원금</dt>
          <dd className="mt-0.5 font-semibold num">
            {formatMoney(summary.total_cost_basis, currency)}
          </dd>
        </div>
        <div>
          <dt className="text-[13px] text-subtle">보유 종목</dt>
          <dd className="mt-0.5 font-semibold num">
            {summary.holding_count}개
            {!summary.is_complete && (
              <span className="ml-1 text-[13px] font-normal text-subtle">
                ({summary.valued_holding_count}개 평가)
              </span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}

/** 총자산 변화. 저장된 기록이 2개 이상일 때만 그린다. */
function HistoryCard({ history }: { history: History }) {
  return (
    <Card
      title="총자산 변화"
      action={history.is_demo ? <DemoBadge label="가상 이력" /> : undefined}
    >
      <PortfolioChart points={history.points} />
    </Card>
  );
}

/** 섹터별 구성. 분석 엔진의 섹터 비중(risk.allocations.sector)을 그린다. */
function SectorCard({
  slices,
  isLoading,
  isError,
  currency,
  centerValue,
  className,
}: {
  className?: string;
  slices: AllocationSlice[] | undefined;
  isLoading: boolean;
  isError: boolean;
  currency: string;
  centerValue: string;
}) {
  const donut = slices ? sectorDonutSlices(slices) : [];
  const allUnclassified = donut.length > 0 && donut.every((s) => s.is_unclassified);
  return (
    <Card
      title="섹터별 구성"
      className={className}
      action={
        <Link href="/analytics" className="text-[13px] text-subtle hover:text-foreground">
          자세히
        </Link>
      }
    >
      {isLoading ? (
        <Skeleton className="mx-auto aspect-square w-full max-w-[220px] rounded-full" />
      ) : isError || !slices ? (
        <EmptyState title="섹터 비중을 불러오지 못했습니다" className="flex-1" />
      ) : donut.length === 0 ? (
        <EmptyState title="표시할 자산이 없습니다" className="flex-1" />
      ) : (
        <>
          <AssetAllocationChart
            slices={donut}
            currency={currency}
            centerLabel="총 평가자산"
            centerValue={centerValue}
            colorOf={(slice) => sectorColor(slice, donut)}
          />
          {allUnclassified && (
            <p className="mt-3 text-[13px] text-subtle">
              섹터 정보가 있는 종목이 없습니다. 해외 개별주는 한국투자증권 업종 분류로 채웁니다.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

export default function DashboardPage() {
  const portfolio = usePortfolio();
  const history = useHistory();
  const risk = useRisk();

  if (portfolio.isPending) return <LoadingSkeleton />;
  if (portfolio.isError) {
    return <QueryError error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  }

  const { data } = portfolio;
  const { summary } = data;
  const currency = summary.valuation_currency;
  const centerValue =
    summary.total_market_value === null
      ? "–"
      : `${formatKrwCompact(Number(summary.total_market_value))}원`;

  const hasHistory = (history.data?.points.length ?? 0) >= 2;

  return (
    <div>
      <DataProvenanceBar portfolio={data} isFetching={portfolio.isFetching} />

      <div className="grid gap-3 md:gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TotalAssetCard summary={summary} />
        </div>
        <SectorCard
          className="lg:row-span-2"
          slices={risk.data?.allocations.sector}
          isLoading={risk.isPending}
          isError={risk.isError}
          currency={currency}
          centerValue={centerValue}
        />
        <Card
          title="비중 큰 종목"
          className="lg:col-span-2"
          action={
            <Link
              href="/holdings"
              className="inline-flex h-9 items-center gap-1 text-[13px] text-subtle hover:text-foreground"
            >
              전체 {data.holdings.length}개 보기
              <ArrowRight className="size-3.5" aria-hidden="true" />
            </Link>
          }
        >
          {data.holdings.length > 0 ? (
            <HoldingValueBars holdings={data.holdings} limit={5} />
          ) : (
            <EmptyState title="보유 종목이 없습니다" />
          )}
        </Card>
      </div>

      <div className="mt-3 grid gap-3 md:mt-4 md:gap-4 lg:grid-cols-3">
        {hasHistory && history.data && (
          <div className="lg:col-span-2">
            <HistoryCard history={history.data} />
          </div>
        )}
        <AIInsightCard
          insights={risk.data?.insights}
          isLoading={risk.isPending}
          isError={risk.isError}
          limit={2}
          className={hasHistory ? undefined : "lg:col-span-3"}
        />
      </div>

      <Assumptions items={data.assumptions} />
    </div>
  );
}
