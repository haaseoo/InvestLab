"use client";

import { Coins, Layers, Percent, TrendingUp, Wallet } from "lucide-react";
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
import { StatCard } from "@/components/stat-card";
import { LoadingSkeleton } from "@/components/state";
import { Skeleton } from "@/components/ui/skeleton";
import { useHistory, usePortfolio, useRisk } from "@/hooks/use-portfolio";
import { sectorColor, sectorDonutSlices } from "@/lib/chart";
import {
  directionOf,
  formatKrwCompact,
  formatMoney,
  formatPercent,
  formatSignedMoney,
  formatSignedPercent,
} from "@/lib/format";
import type { History, PortfolioSummary } from "@/types/portfolio";
import type { AllocationSlice } from "@/types/portfolio";

function pnlWord(value: string | null) {
  const direction = directionOf(value);
  if (direction === "up") return "평가이익";
  if (direction === "down") return "평가손실";
  return direction === "flat" ? "손익 없음" : "계산 불가";
}

const CURRENCY_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)"];

/** 총 평가자산. 숫자 옆에 거래 통화 구성(분석 엔진 계산값)을 함께 둬 가로 공간을 쓴다. */
function TotalAssetCard({
  summary,
  currencySlices,
}: {
  summary: PortfolioSummary;
  currencySlices: AllocationSlice[] | undefined;
}) {
  const currency = summary.valuation_currency;
  return (
    <section className="flex flex-col gap-4 card-surface p-5 md:flex-row md:items-center md:justify-between md:gap-8 md:p-6">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-full bg-secondary">
            <Wallet className="size-4 text-faint" aria-hidden="true" />
          </span>
          <h2 className="text-[15px] font-medium text-subtle">총 평가자산</h2>
        </div>
        <p className="mt-2 text-[28px] leading-tight font-bold num tracking-tight md:text-[34px]">
          {formatMoney(summary.total_market_value, currency)}
        </p>
        <p className="mt-1 text-[13px] text-subtle">
          {currency} 환산 · 예수금 제외 ·{" "}
          <PnlText
            value={summary.total_unrealized_pnl_pct}
            text={formatSignedPercent(summary.total_unrealized_pnl_pct)}
            className="font-semibold"
          />
        </p>
      </div>

      {currencySlices && currencySlices.length > 0 && (
        <div className="w-full md:max-w-sm">
          <h3 className="mb-2 text-[13px] text-subtle">거래 통화 구성</h3>
          <div className="flex h-2 gap-0.5 overflow-hidden rounded-full">
            {currencySlices.map((slice, i) => (
              <div
                key={slice.key}
                style={{
                  width: `${Number(slice.weight_pct)}%`,
                  background: CURRENCY_COLORS[i % CURRENCY_COLORS.length],
                }}
              />
            ))}
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
            {currencySlices.map((slice, i) => (
              <li key={slice.key} className="flex items-center gap-1.5">
                <span
                  className="size-2 rounded-full"
                  style={{ background: CURRENCY_COLORS[i % CURRENCY_COLORS.length] }}
                  aria-hidden="true"
                />
                <span className="text-subtle">{slice.label}</span>
                <span className="font-semibold num">{formatPercent(slice.weight_pct)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
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

/** 섹터별 구성. 분석 엔진의 섹터 비중(risk.allocations.sector)을 그린다. */
function SectorCard({
  slices,
  isLoading,
  isError,
  currency,
  centerValue,
}: {
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

  return (
    <div>
      <DataProvenanceBar portfolio={data} isFetching={portfolio.isFetching} />

      <TotalAssetCard summary={summary} currencySlices={risk.data?.allocations.currency} />

      <div className="mt-3 grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:mt-4 md:gap-4 xl:grid-cols-4">
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
        <SectorCard
          slices={risk.data?.allocations.sector}
          isLoading={risk.isPending}
          isError={risk.isError}
          currency={currency}
          centerValue={centerValue}
        />
      </div>

      <div className="mt-3 grid gap-3 md:mt-4 md:gap-4 lg:grid-cols-3">
        <Card title="종목별 평가금액" className="lg:col-span-2">
          {data.holdings.length > 0 ? (
            <HoldingValueBars holdings={data.holdings} />
          ) : (
            <EmptyState title="보유 종목이 없습니다" />
          )}
        </Card>
        <AIInsightCard
          insights={risk.data?.insights}
          isLoading={risk.isPending}
          isError={risk.isError}
          limit={4}
          showLink
        />
      </div>

      {/* 지금 연결된 계좌는 해외 개별주만이라 자산군 구성은 보조 정보로 아래에 둔다. */}
      <div className="mt-3 grid gap-3 md:mt-4 md:gap-4 lg:grid-cols-3">
        <Card title="자산 구성">
          {data.allocation.length > 0 ? (
            <AssetAllocationChart
              slices={data.allocation}
              currency={currency}
              centerLabel="총 평가자산"
              centerValue={centerValue}
            />
          ) : (
            <EmptyState title="표시할 자산이 없습니다" className="flex-1" />
          )}
        </Card>
      </div>

      <Assumptions items={data.assumptions} />
    </div>
  );
}
