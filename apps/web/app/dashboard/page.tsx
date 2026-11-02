"use client";

import { Coins, Layers, Percent, TrendingUp, Wallet } from "lucide-react";

import { AIInsightCard } from "@/components/ai-insight-card";
import { AssetAllocationChart } from "@/components/asset-allocation-chart";
import { Card, DemoBadge } from "@/components/card";
import { Assumptions, DataProvenanceBar } from "@/components/data-provenance";
import { HoldingValueBars } from "@/components/holding-value-bars";
import { PnlText } from "@/components/pnl-text";
import { PortfolioChart } from "@/components/portfolio-chart";
import { QueryError } from "@/components/query-error";
import { StatCard } from "@/components/stat-card";
import { EmptyState } from "@/components/empty-state";
import { LoadingSkeleton } from "@/components/state";
import { useHistory, usePortfolio } from "@/hooks/use-portfolio";
import {
  directionOf,
  formatKrwCompact,
  formatMoney,
  formatSignedMoney,
  formatSignedPercent,
} from "@/lib/format";
import type { History } from "@/types/portfolio";

function pnlWord(value: string | null) {
  const direction = directionOf(value);
  if (direction === "up") return "평가이익";
  if (direction === "down") return "평가손실";
  return direction === "flat" ? "손익 없음" : "계산 불가";
}

function HistoryCard({
  history,
  isError,
  isLoading,
}: {
  history: History | undefined;
  isError: boolean;
  isLoading: boolean;
}) {
  const hasEnough = (history?.points.length ?? 0) >= 2;
  return (
    <Card
      title="총자산 변화"
      action={history?.is_demo && hasEnough ? <DemoBadge label="가상 이력" /> : undefined}
      className="lg:col-span-2"
    >
      {hasEnough && history ? (
        <PortfolioChart points={history.points} />
      ) : (
        <EmptyState
          title={
            isLoading
              ? "이력을 불러오는 중입니다"
              : isError
                ? "이력을 불러오지 못했습니다"
                : "기록이 부족합니다"
          }
          description={
            isLoading || isError
              ? undefined
              : "저장된 스냅샷이 2개 이상 쌓이면 변화 추이를 표시합니다. 임의의 과거 실적을 만들지 않습니다."
          }
          className="flex-1"
        />
      )}
    </Card>
  );
}

export default function DashboardPage() {
  const portfolio = usePortfolio();
  const history = useHistory();

  if (portfolio.isPending) return <LoadingSkeleton />;
  if (portfolio.isError) {
    return <QueryError error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  }

  const { data } = portfolio;
  const { summary } = data;
  const currency = summary.valuation_currency;

  return (
    <div>
      <DataProvenanceBar portfolio={data} isFetching={portfolio.isFetching} />

      <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:gap-4 lg:grid-cols-[1.3fr_1fr_1fr]">
        <StatCard
          label="총 평가자산"
          icon={Wallet}
          value={
            <span className="text-[26px] md:text-[28px] lg:text-[32px] xl:text-[38px]">
              {formatMoney(summary.total_market_value, currency)}
            </span>
          }
          hint={`${currency} 환산 · 예수금 제외`}
          className="justify-between min-[360px]:col-span-2 lg:col-span-1 lg:row-span-2"
        />
        <StatCard
          label="총 투자 원금"
          icon={Coins}
          value={formatMoney(summary.total_cost_basis, currency)}
          hint="평균단가 × 수량"
        />
        <StatCard
          label="총 평가손익"
          icon={TrendingUp}
          value={
            <PnlText
              value={summary.total_unrealized_pnl}
              text={formatSignedMoney(summary.total_unrealized_pnl, currency)}
            />
          }
          hint={pnlWord(summary.total_unrealized_pnl)}
        />
        <StatCard
          label="총 수익률"
          icon={Percent}
          value={
            <PnlText
              value={summary.total_unrealized_pnl_pct}
              text={formatSignedPercent(summary.total_unrealized_pnl_pct)}
            />
          }
          hint="평가손익 기준"
        />
        <StatCard
          label="보유 종목 수"
          icon={Layers}
          value={`${summary.holding_count}개`}
          hint={
            summary.is_complete ? "전 종목 평가 완료" : `${summary.valued_holding_count}개만 평가됨`
          }
        />
      </div>

      <div className="mt-3 grid gap-3 md:mt-4 md:gap-4 lg:grid-cols-3">
        <HistoryCard
          history={history.data}
          isError={history.isError}
          isLoading={history.isPending}
        />
        <Card title="자산 구성">
          {data.allocation.length > 0 ? (
            <AssetAllocationChart
              slices={data.allocation}
              currency={currency}
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
      </div>

      <div className="mt-3 grid gap-3 md:mt-4 md:gap-4 lg:grid-cols-3">
        <Card title="종목별 평가금액" className="lg:col-span-2">
          {data.holdings.length > 0 ? (
            <HoldingValueBars holdings={data.holdings} />
          ) : (
            <EmptyState title="보유 종목이 없습니다" />
          )}
        </Card>
        <AIInsightCard />
      </div>

      <Assumptions items={data.assumptions} />
    </div>
  );
}
