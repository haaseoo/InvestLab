"use client";

import { useState } from "react";

import { Card } from "@/components/card";
import { DataProvenanceBar } from "@/components/data-provenance";
import { QueryError } from "@/components/query-error";
import { BuySimulator } from "@/components/simulator/buy-simulator";
import { RebalanceSimulator } from "@/components/simulator/rebalance-simulator";
import { ScenarioSimulator } from "@/components/simulator/scenario-simulator";
import { LoadingSkeleton } from "@/components/state";
import { usePortfolio } from "@/hooks/use-portfolio";
import { useSource } from "@/hooks/use-source";
import { cn } from "@/lib/utils";

const TABS = [
  ["buy", "추가 매수"],
  ["rebalance", "리밸런싱"],
  ["scenario", "하락 시나리오"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function SimulatorPage() {
  const portfolio = usePortfolio();
  const { source } = useSource();
  const [tab, setTab] = useState<Tab>("buy");

  if (portfolio.isPending) return <LoadingSkeleton variant="table" />;
  if (portfolio.isError) {
    return <QueryError error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  }

  const { data } = portfolio;
  const currency = data.valuation_currency;

  return (
    <div>
      <DataProvenanceBar portfolio={data} isFetching={portfolio.isFetching} />

      <div role="tablist" aria-label="시뮬레이션 종류" className="mb-4 flex gap-1 overflow-x-auto">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            id={`tab-${value}`}
            aria-selected={tab === value}
            aria-controls={`panel-${value}`}
            onClick={() => setTab(value)}
            className={cn(
              "h-10 shrink-0 rounded-full px-4 text-sm font-semibold transition-colors",
              tab === value
                ? "bg-primary text-primary-foreground"
                : "text-subtle hover:bg-secondary hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* source가 바뀌면 입력과 결과를 모두 초기화한다. 다른 모드의 결과가 남지 않게 한다. */}
      <Card className="min-h-96" key={source}>
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === "buy" && <BuySimulator holdings={data.holdings} valuationCurrency={currency} />}
          {tab === "rebalance" && (
            <RebalanceSimulator
              holdings={data.holdings}
              allocation={data.allocation}
              currency={currency}
            />
          )}
          {tab === "scenario" && (
            <ScenarioSimulator
              holdings={data.holdings}
              allocation={data.allocation}
              currency={currency}
            />
          )}
        </div>
      </Card>

      <p className="mt-4 px-1 text-xs leading-relaxed text-subtle">
        모든 결과는 현재 보유 데이터에 가정을 적용한 계산이며 실제 주문을 실행하지 않습니다. 미래
        수익이나 주가를 예측하지 않으며 투자 권유가 아닙니다.
      </p>
    </div>
  );
}
