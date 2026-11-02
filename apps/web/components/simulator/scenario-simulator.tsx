"use client";

import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { PnlText } from "@/components/pnl-text";
import {
  AssumptionList,
  DecimalInput,
  Field,
  ResultTable,
  SimulationError,
  SubmitButton,
  TheoreticalBadge,
} from "@/components/simulator/sim-ui";
import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";
import { formatMoney, formatPercent, formatSignedMoney, formatSignedPercent } from "@/lib/format";
import type { ScenarioRequest, ScenarioResult } from "@/types/analysis";
import type { AllocationSlice, Holding } from "@/types/portfolio";

const SOURCE_LABEL = { holding: "종목 지정", asset_class: "자산군", none: "변화 없음" } as const;

function ScenarioResultView({ result, currency }: { result: ScenarioResult; currency: string }) {
  const changed = result.rows.filter(
    (r) => Number(r.price_change_pct) !== 0 || Number(r.fx_change_pct) !== 0,
  );
  // 환율 가정이 없으면 0%만 반복되는 열을 숨긴다.
  const hasFx = changed.some((r) => Number(r.fx_change_pct) !== 0);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[15px] font-semibold">가정 적용 결과</h3>
        <TheoreticalBadge />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ["현재 평가자산", formatMoney(result.total_before, currency), null],
          ["가정 적용 후", formatMoney(result.total_after, currency), null],
          [
            "변화",
            formatSignedMoney(result.total_change, currency),
            formatSignedPercent(result.total_change_pct),
          ],
        ].map(([label, value, sub]) => (
          <div key={label} className="rounded-xl border p-4">
            <p className="text-[13px] text-subtle">{label}</p>
            <p className="mt-1 text-lg font-bold num">
              {sub ? <PnlText value={result.total_change} text={value as string} /> : value}
            </p>
            {sub && <PnlText value={result.total_change_pct} text={sub} className="text-[13px]" />}
          </div>
        ))}
      </div>

      {changed.length > 0 && (
        <ResultTable
          caption="종목별 가정 적용 결과"
          head={[
            { label: "종목" },
            { label: "가격 변화", numeric: true },
            ...(hasFx ? [{ label: "환율 변화", numeric: true }] : []),
            { label: "적용 전", numeric: true },
            { label: "적용 후", numeric: true },
            { label: "영향", numeric: true },
          ]}
          minWidth={hasFx ? 680 : 600}
        >
          {changed.map((row) => (
            <tr key={row.key}>
              <th scope="row" className="text-left font-medium">
                <span className="block max-w-44 truncate">{row.name}</span>
                <span className="block text-xs font-normal text-subtle">
                  {SOURCE_LABEL[row.price_change_source]}
                </span>
              </th>
              <td className="text-right num">{formatSignedPercent(row.price_change_pct)}</td>
              {hasFx && (
                <td className="text-right num">{formatSignedPercent(row.fx_change_pct)}</td>
              )}
              <td className="text-right num">{formatMoney(row.value_before, currency)}</td>
              <td className="text-right num">{formatMoney(row.value_after, currency)}</td>
              <td className="text-right font-semibold">
                <PnlText value={row.impact} text={formatSignedMoney(row.impact, currency)} />
              </td>
            </tr>
          ))}
        </ResultTable>
      )}

      {result.standalone_change_pct !== null && (
        <section>
          <h4 className="mb-2 text-sm font-semibold">
            종목별 민감도 · 한 종목만 {formatSignedPercent(result.standalone_change_pct)} 변할 때
          </h4>
          <ResultTable
            caption="종목별 단독 변화 시 전체 영향"
            head={[
              { label: "종목" },
              { label: "비중", numeric: true },
              { label: "평가자산 영향", numeric: true },
              { label: "전체 대비", numeric: true },
            ]}
            minWidth={520}
          >
            {result.standalone.map((row) => (
              <tr key={row.key}>
                <th scope="row" className="max-w-56 truncate text-left font-medium">
                  {row.name}
                </th>
                <td className="text-right num">{formatPercent(row.weight_pct)}</td>
                <td className="text-right">
                  <PnlText value={row.impact} text={formatSignedMoney(row.impact, currency)} />
                </td>
                <td className="text-right">
                  <PnlText
                    value={row.impact_on_total_pct}
                    text={formatSignedPercent(row.impact_on_total_pct)}
                  />
                </td>
              </tr>
            ))}
          </ResultTable>
        </section>
      )}
      <AssumptionList items={result.assumptions} />
    </div>
  );
}

export function ScenarioSimulator({
  holdings,
  allocation,
  currency,
}: {
  holdings: Holding[];
  allocation: AllocationSlice[];
  currency: string;
}) {
  const { source } = useSource();
  const [classShocks, setClassShocks] = useState<Record<string, string>>({});
  const [holdingShocks, setHoldingShocks] = useState<Record<string, string>>({});
  const [fxShocks, setFxShocks] = useState<Record<string, string>>({});
  const [standalone, setStandalone] = useState("-20");

  const mutation = useMutation({
    mutationFn: (body: ScenarioRequest) => api.simulateScenario(source, body),
  });

  const foreignCurrencies = [
    ...new Set(holdings.filter((h) => h.currency !== currency).map((h) => h.currency)),
  ];
  const valued = holdings.filter((h) => h.market_value_valuation !== null);

  const entries = (record: Record<string, string>) =>
    Object.entries(record).filter(([, v]) => v.trim() !== "");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate({
      shocks: [
        ...entries(classShocks).map(([key, change_pct]) => ({
          type: "asset_class" as const,
          key,
          change_pct,
        })),
        ...entries(holdingShocks).map(([key, change_pct]) => ({
          type: "holding" as const,
          key,
          change_pct,
        })),
      ],
      fx_shocks: entries(fxShocks).map(([c, change_pct]) => ({ currency: c, change_pct })),
      ...(standalone.trim() ? { standalone_change_pct: standalone } : {}),
    });
  };

  const preset = (pct: string) =>
    setClassShocks(Object.fromEntries(allocation.map((s) => [s.key, pct])));

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,400px)_1fr]">
      <form onSubmit={submit} className="space-y-5">
        <fieldset className="space-y-2.5">
          <legend className="mb-2 text-sm font-semibold">자산군별 가정 변화율</legend>
          <div className="flex flex-wrap gap-2">
            {["-10", "-20", "-30"].map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => preset(p)}
                className="h-9 rounded-full border px-3.5 text-[13px] font-medium num hover:bg-secondary"
              >
                전체 {p}%
              </button>
            ))}
            <button
              type="button"
              onClick={() => setClassShocks({})}
              className="h-9 rounded-full border px-3.5 text-[13px] font-medium hover:bg-secondary"
            >
              비우기
            </button>
          </div>
          {allocation.map((s) => (
            <div key={s.key} className="flex items-center gap-3">
              <span className="min-w-0 flex-1 truncate text-sm">
                {s.label}{" "}
                <span className="text-xs num text-subtle">{formatPercent(s.weight_pct)}</span>
              </span>
              <div className="w-28 shrink-0">
                <DecimalInput
                  value={classShocks[s.key] ?? ""}
                  onChange={(v) => setClassShocks((prev) => ({ ...prev, [s.key]: v }))}
                  suffix="%"
                  placeholder="0"
                  ariaLabel={`${s.label} 가정 변화율`}
                />
              </div>
            </div>
          ))}
        </fieldset>

        <details className="rounded-xl border px-3.5 py-2.5">
          <summary className="cursor-pointer text-sm font-semibold">
            종목별 가정 변화율 <span className="font-normal text-subtle">(자산군보다 우선)</span>
          </summary>
          <div className="mt-3 max-h-72 space-y-2 overflow-y-auto">
            {valued.map((h) => {
              const key = `${h.market}:${h.symbol}`;
              return (
                <div key={key} className="flex items-center gap-3">
                  <span className="min-w-0 flex-1 truncate text-sm">{h.name}</span>
                  <div className="w-28 shrink-0">
                    <DecimalInput
                      value={holdingShocks[key] ?? ""}
                      onChange={(v) => setHoldingShocks((prev) => ({ ...prev, [key]: v }))}
                      suffix="%"
                      placeholder="–"
                      ariaLabel={`${h.name} 가정 변화율`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </details>

        {foreignCurrencies.map((c) => (
          <Field key={c} label={`${c} 환율 변화율`} hint={`${c}로 거래되는 종목에만 적용합니다.`}>
            <DecimalInput
              value={fxShocks[c] ?? ""}
              onChange={(v) => setFxShocks((prev) => ({ ...prev, [c]: v }))}
              suffix="%"
              placeholder="0"
              ariaLabel={`${c} 환율 변화율`}
            />
          </Field>
        ))}

        <Field
          label="종목별 민감도"
          hint="각 종목이 혼자 이만큼 변할 때의 영향을 따로 계산합니다. 비우면 생략합니다."
        >
          <DecimalInput
            value={standalone}
            onChange={setStandalone}
            suffix="%"
            ariaLabel="종목별 민감도 변화율"
          />
        </Field>

        <SubmitButton pending={mutation.isPending}>시나리오 계산</SubmitButton>
        <SimulationError error={mutation.error} />
      </form>

      <div className="min-w-0">
        {mutation.data ? (
          <ScenarioResultView result={mutation.data} currency={currency} />
        ) : (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-subtle">
            가정 변화율을 입력하고 계산하면 전체 평가자산 변화와 종목별 영향이 여기에 표시됩니다.
            예측이 아니라 가정에 따른 계산입니다.
          </p>
        )}
      </div>
    </div>
  );
}
