"use client";

import { CircleSlash } from "lucide-react";

import { AllocationBars } from "@/components/allocation-bars";
import { AssetAllocationChart } from "@/components/asset-allocation-chart";
import { Card } from "@/components/card";
import { Assumptions, DataProvenanceBar } from "@/components/data-provenance";
import { QueryError } from "@/components/query-error";
import { RiskIndicator } from "@/components/risk-indicator";
import { LoadingSkeleton } from "@/components/state";
import { usePortfolio, useRisk } from "@/hooks/use-portfolio";
import { formatKrwCompact, formatMoney, formatPercent, MISSING } from "@/lib/format";
import type { ConstituentOverlap, Risk } from "@/types/analysis";
import type { AllocationSlice } from "@/types/portfolio";

const OVERLAP_STATUS: Record<ConstituentOverlap["status"], string> = {
  not_applicable: "보유 ETF가 없어 해당하지 않습니다.",
  unavailable: "보유 ETF의 구성 종목 데이터가 없어 계산하지 않았습니다.",
  partial: "일부 ETF만 구성 종목 데이터가 있어 그 ETF만 반영했습니다.",
  complete: "모든 보유 ETF의 구성 종목 데이터를 반영했습니다.",
};

function Note({ children }: { children: React.ReactNode }) {
  return <p className="mt-4 text-xs leading-relaxed text-subtle">{children}</p>;
}

function ConcentrationCard({ risk }: { risk: Risk }) {
  const c = risk.concentration;
  return (
    <Card title="종목 집중도">
      <div className="space-y-5">
        <RiskIndicator
          label="최대 보유 종목"
          valuePct={c.top1_pct}
          description="평가금액이 가장 큰 1개 종목의 비중"
        />
        <RiskIndicator
          label="상위 3개 종목"
          valuePct={c.top3_pct}
          description="평가금액 상위 3개 종목의 비중 합"
        />
        <RiskIndicator
          label="상위 5개 종목"
          valuePct={c.top5_pct}
          description="평가금액 상위 5개 종목의 비중 합"
        />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-secondary/70 p-3.5">
          <dt className="text-[13px] text-subtle">HHI</dt>
          <dd className="mt-0.5 text-lg font-bold num">
            {c.hhi === null
              ? MISSING
              : Number(c.hhi).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
          </dd>
        </div>
        <div className="rounded-xl bg-secondary/70 p-3.5">
          <dt className="text-[13px] text-subtle">유효 종목 수</dt>
          <dd className="mt-0.5 text-lg font-bold num">
            {c.effective_holdings === null
              ? MISSING
              : `${Number(c.effective_holdings).toFixed(1)}개`}
          </dd>
        </div>
      </dl>
      <Note>
        HHI는 종목 비중(%)의 제곱합으로 0~10,000 사이 값이며, 유효 종목 수는 10,000 ÷ HHI입니다.
        보유 종목 단위 계산이며 ETF 내부 편입 종목은 펼치지 않았습니다.
      </Note>
    </Card>
  );
}

function OverlapCard({ risk }: { risk: Risk }) {
  const { benchmark_groups: groups, constituent_overlap: constituent } = risk.overlap;
  const currency = risk.valuation_currency;
  return (
    <Card title="ETF 중복 투자" className="lg:col-span-2">
      <div className="grid gap-6 md:grid-cols-2">
        <section>
          <h3 className="text-[15px] font-semibold">동일 지수 추종</h3>
          <p className="mt-1 mb-3 text-[13px] text-subtle">
            추종 지수 정보만으로 판단합니다. 같은 지수를 따르는 ETF를 여러 개 보유한 경우입니다.
          </p>
          {groups.length === 0 ? (
            <p className="text-sm text-subtle">같은 지수를 추종하는 ETF 묶음이 없습니다.</p>
          ) : (
            <ul className="space-y-3">
              {groups.map((group) => (
                <li key={group.benchmark} className="rounded-xl border p-3.5">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-semibold">{group.benchmark}</span>
                    <span className="text-sm font-semibold num">
                      합계 {formatPercent(group.combined_weight_pct)}
                    </span>
                  </div>
                  <ul className="mt-2 space-y-1 text-[13px]">
                    {group.holdings.map((h) => (
                      <li key={`${h.market}:${h.symbol}`} className="flex justify-between gap-3">
                        <span className="truncate text-subtle">
                          {h.name} <span className="num">({h.symbol})</span>
                        </span>
                        <span className="num">{formatPercent(h.weight_pct)}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="text-[15px] font-semibold">구성 종목 중복</h3>
          <p className="mt-1 mb-3 text-[13px] text-subtle">
            ETF 구성 종목을 펼쳐 같은 기초 종목에 여러 경로로 노출된 금액을 계산합니다.
          </p>
          {constituent.overlaps.length === 0 ? (
            <div className="flex items-start gap-3 rounded-xl bg-secondary/70 p-3.5">
              <CircleSlash className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden="true" />
              <div className="text-[13px]">
                <p className="font-medium">{OVERLAP_STATUS[constituent.status]}</p>
                {constituent.missing_etfs.length > 0 && (
                  <p className="mt-1 text-subtle">
                    데이터 없음: <span className="num">{constituent.missing_etfs.join(", ")}</span>
                  </p>
                )}
                <p className="mt-1 text-subtle">
                  구성 종목 데이터를 임의로 만들지 않습니다. 데이터 출처가 연결되면 계산합니다.
                </p>
              </div>
            </div>
          ) : (
            <>
              <p className="mb-2 text-[13px] text-subtle">{OVERLAP_STATUS[constituent.status]}</p>
              <ul className="space-y-2 text-sm">
                {constituent.overlaps.map((o) => (
                  <li key={`${o.market}:${o.symbol}`} className="flex justify-between gap-3">
                    <span className="truncate">
                      {o.name}
                      <span className="ml-1.5 text-xs text-subtle">
                        {o.paths.map((p) => (p.via === "direct" ? "직접" : p.via)).join(" + ")}
                      </span>
                    </span>
                    <span className="shrink-0 num">
                      {formatMoney(o.total_value, currency)} · {formatPercent(o.weight_pct)}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </Card>
  );
}

/** 한 칸이 100%인 분포는 차트로 보여 줄 정보가 없다. */
function isSingle(slices: AllocationSlice[]) {
  return slices.length <= 1;
}

function hasEtfOverlapInfo(risk: Risk) {
  const { benchmark_groups: groups, constituent_overlap: constituent } = risk.overlap;
  return groups.length > 0 || constituent.status !== "not_applicable";
}

export default function AnalyticsPage() {
  const portfolio = usePortfolio();
  const risk = useRisk();

  if (portfolio.isPending || risk.isPending) return <LoadingSkeleton />;
  if (portfolio.isError) {
    return <QueryError error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  }
  if (risk.isError) {
    return <QueryError error={risk.error} onRetry={() => risk.refetch()} />;
  }

  const { summary } = portfolio.data;
  const r = risk.data;
  const currency = r.valuation_currency;
  const { asset_class: assetClass, exposure_country: country, currency: fx } = r.allocations;

  // 한 가지뿐이라 생략한 분포. 생략했다는 사실은 한 줄로 알린다.
  const omitted = [
    isSingle(assetClass) && assetClass[0] && `자산군(${assetClass[0].label})`,
    isSingle(country) && country[0] && `국가(${country[0].label})`,
    isSingle(fx) && fx[0] && `거래 통화(${fx[0].label})`,
  ].filter(Boolean) as string[];

  return (
    <div>
      <DataProvenanceBar portfolio={portfolio.data} isFetching={risk.isFetching} />
      <div className="grid gap-3 md:gap-4 lg:grid-cols-2">
        <Card title="섹터별 비중">
          <AllocationBars
            slices={r.allocations.sector}
            currency={currency}
            color="var(--chart-3)"
            showSymbols
          />
          <Note>
            개별 종목과 섹터 ETF만 섹터로 분류했습니다. 여러 섹터에 걸친 지수 ETF는 구성 종목
            데이터가 없어 &lsquo;섹터 정보 없음&rsquo;으로 묶었으며, 그 안의 섹터 노출은 위 비중에
            포함되지 않습니다.
          </Note>
        </Card>

        <ConcentrationCard risk={r} />

        {!isSingle(country) && (
          <Card title="국가별 비중">
            <AllocationBars slices={country} currency={currency} />
            <Note>
              투자 대상 국가 기준입니다. 국내에 상장된 해외지수 ETF는 추종 지수의 국가로
              분류했습니다. 금 등 국가로 나눌 수 없는 자산은 따로 표시합니다.
            </Note>
          </Card>
        )}

        {!isSingle(assetClass) && (
          <Card title="자산군별 비중">
            <AssetAllocationChart
              slices={assetClass}
              currency={currency}
              centerLabel="총 평가자산"
              centerValue={
                summary.total_market_value === null
                  ? MISSING
                  : `${formatKrwCompact(Number(summary.total_market_value))}원`
              }
            />
          </Card>
        )}

        {!isSingle(fx) && (
          <Card title="거래 통화별 비중">
            <AllocationBars slices={fx} currency={currency} color="var(--chart-2)" />
            <Note>
              거래 통화 기준입니다. 원화로 거래되는 해외 ETF의 환 노출과 환헤지 여부는 반영하지
              않았습니다.
            </Note>
          </Card>
        )}

        {hasEtfOverlapInfo(r) && <OverlapCard risk={r} />}
      </div>

      {omitted.length > 0 && (
        <p className="mt-4 px-1 text-[13px] text-subtle">
          한 가지뿐이라 비중 차트를 생략한 항목: {omitted.join(", ")}
        </p>
      )}

      <Assumptions items={r.assumptions}>
        {r.unavailable_metrics.length > 0 && (
          <>
            <h3 className="mt-4 mb-1 text-[13px] font-semibold text-subtle">계산하지 않은 지표</h3>
            <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-subtle">
              {r.unavailable_metrics.map((metric) => (
                <li key={metric.key}>
                  {metric.label}: {metric.reason}
                </li>
              ))}
            </ul>
          </>
        )}
      </Assumptions>
    </div>
  );
}
