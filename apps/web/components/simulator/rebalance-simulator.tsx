"use client";

import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useMemo, useState } from "react";

import { PnlText } from "@/components/pnl-text";
import { SaveSimulation } from "@/components/simulator/save-simulation";
import {
  AssumptionList,
  DecimalInput,
  Field,
  ResultTable,
  Segmented,
  SimulationError,
  SubmitButton,
  TheoreticalBadge,
} from "@/components/simulator/sim-ui";
import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";
import {
  formatMoney,
  formatPercent,
  formatQuantity,
  formatSignedMoney,
  formatSignedPercent,
  MISSING,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type { RebalanceRequest, RebalanceResult } from "@/types/analysis";
import type { AllocationSlice, Holding } from "@/types/portfolio";

type Dimension = RebalanceRequest["dimension"];
interface Row {
  key: string;
  label: string;
  currentPct: string;
}

/**
 * 현재 비중을 소수 둘째 자리로 맞춰 시작값으로 쓴다. 반올림 때문에 합이 100.00이 아니면
 * 차이를 가장 큰 항목에 더한다. 계산은 0.01% 단위 정수로 해서 부동소수점 오차가 없다.
 */
function prefill(rows: Row[]): Record<string, string> {
  const cents = rows.map((r) => Math.round(Number(r.currentPct) * 100));
  const diff = 10000 - cents.reduce((a, b) => a + b, 0);
  if (cents.length > 0) {
    const largest = cents.indexOf(Math.max(...cents));
    cents[largest] += diff;
  }
  return Object.fromEntries(rows.map((r, i) => [r.key, (cents[i] / 100).toFixed(2)]));
}

function toCents(value: string): number | null {
  if (value.trim() === "") return 0;
  const n = Number(value);
  return Number.isFinite(n) ? Math.round(n * 100) : null;
}

function RebalanceResultView({ result, currency }: { result: RebalanceResult; currency: string }) {
  const byHolding = result.dimension === "holding";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-subtle">
          조정 후 총액{" "}
          <span className="font-semibold num text-foreground">
            {formatMoney(result.total_after, currency)}
          </span>
          {Number(result.additional_cash) > 0 &&
            ` (추가 현금 ${formatMoney(result.additional_cash, currency)} 포함)`}
        </p>
        <TheoreticalBadge />
      </div>

      <ResultTable
        caption="리밸런싱 조정 결과"
        head={[
          { label: "항목" },
          { label: "현재 비중", numeric: true },
          { label: "목표 비중", numeric: true },
          { label: "차이", numeric: true },
          { label: "가상 조정 금액", numeric: true },
          ...(byHolding ? [{ label: "이론 수량", numeric: true }] : []),
        ]}
        minWidth={byHolding ? 720 : 560}
      >
        {result.rows.map((row) => (
          <tr key={row.key}>
            <th scope="row" className="max-w-56 truncate text-left font-medium">
              {row.label}
              {row.implicit_target && (
                <span className="ml-1.5 text-xs font-normal text-subtle">(목표 미입력 → 0%)</span>
              )}
            </th>
            <td className="text-right num">{formatPercent(row.current_pct)}</td>
            <td className="text-right num">{formatPercent(row.target_pct)}</td>
            <td className="text-right num text-subtle">{formatSignedPercent(row.diff_pct)}p</td>
            <td className="text-right font-semibold">
              <PnlText
                value={row.adjustment_value}
                text={formatSignedMoney(row.adjustment_value, currency)}
              />
            </td>
            {byHolding && (
              <td className="text-right num text-subtle">
                {row.theoretical_quantity === null
                  ? MISSING
                  : `${Number(row.theoretical_quantity) > 0 ? "+" : ""}${formatQuantity(
                      Number(row.theoretical_quantity).toFixed(4),
                    )}주`}
              </td>
            )}
          </tr>
        ))}
      </ResultTable>
      <p className="text-xs text-subtle">
        조정 금액의 + 는 늘려야 하는 금액, - 는 줄여야 하는 금액입니다. 색은 방향만 나타내며 손익이
        아닙니다.
      </p>
      <AssumptionList items={result.assumptions} />
      <AssumptionList title="반영하지 않은 실제 제약" items={result.constraints_not_applied} />
    </div>
  );
}

export function RebalanceSimulator({
  holdings,
  allocation,
  currency,
}: {
  holdings: Holding[];
  allocation: AllocationSlice[];
  currency: string;
}) {
  const { source } = useSource();
  const [dimension, setDimension] = useState<Dimension>("asset_class");

  const rows: Row[] = useMemo(
    () =>
      dimension === "holding"
        ? holdings
            .filter((h) => h.weight_pct !== null)
            .sort((a, b) => Number(b.weight_pct) - Number(a.weight_pct))
            .map((h) => ({
              key: `${h.market}:${h.symbol}`,
              label: h.name,
              currentPct: h.weight_pct as string,
            }))
        : allocation.map((s) => ({ key: s.key, label: s.label, currentPct: s.weight_pct })),
    [dimension, holdings, allocation],
  );

  const [targetsByDimension, setTargets] = useState<Record<Dimension, Record<string, string>>>(
    () => ({ holding: {}, asset_class: {} }),
  );
  const defaults = useMemo(() => prefill(rows), [rows]);
  const targets = { ...defaults, ...targetsByDimension[dimension] };
  const [cash, setCash] = useState("0");

  const mutation = useMutation({
    mutationFn: (body: RebalanceRequest) => api.simulateRebalance(source, body),
  });

  const cents = rows.map((r) => toCents(targets[r.key] ?? ""));
  const invalid = cents.some((c) => c === null);
  const sumCents = cents.reduce<number>((a, b) => a + (b ?? 0), 0);
  const sumOk = !invalid && sumCents === 10000;

  const setTarget = (key: string, value: string) =>
    setTargets((prev) => ({ ...prev, [dimension]: { ...prev[dimension], [key]: value } }));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate({
      dimension,
      targets: rows
        .filter((r) => (targets[r.key] ?? "").trim() !== "")
        .map((r) => ({ key: r.key, target_pct: targets[r.key] })),
      additional_cash: cash.trim() || "0",
    });
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,400px)_1fr]">
      <form onSubmit={submit} className="space-y-4">
        <Segmented
          label="리밸런싱 단위"
          value={dimension}
          onChange={(d) => {
            setDimension(d);
            mutation.reset();
          }}
          options={[
            ["asset_class", "자산군"],
            ["holding", "종목"],
          ]}
        />

        <fieldset className="rounded-xl border">
          <legend className="sr-only">목표 비중</legend>
          <div className="flex justify-between border-b px-3.5 py-2 text-xs text-subtle">
            <span>항목 · 현재 비중</span>
            <span>목표 비중</span>
          </div>
          <ul className="max-h-[420px] divide-y overflow-y-auto">
            {rows.map((row) => (
              <li key={row.key} className="flex items-center gap-3 px-3.5 py-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{row.label}</p>
                  <p className="text-xs num text-subtle">현재 {formatPercent(row.currentPct)}</p>
                </div>
                <div className="w-28 shrink-0">
                  <DecimalInput
                    value={targets[row.key] ?? ""}
                    onChange={(v) => setTarget(row.key, v)}
                    suffix="%"
                    ariaLabel={`${row.label} 목표 비중`}
                  />
                </div>
              </li>
            ))}
          </ul>
          <div
            className={cn(
              "flex justify-between border-t px-3.5 py-2.5 text-sm",
              sumOk ? "text-subtle" : "font-semibold text-coral-strong",
            )}
            role="status"
          >
            <span>목표 합계</span>
            <span className="num">
              {invalid ? "숫자를 확인하세요" : `${(sumCents / 100).toFixed(2)}%`}
            </span>
          </div>
        </fieldset>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setTargets((prev) => ({ ...prev, [dimension]: {} }))}
            className="h-9 rounded-full border px-3.5 text-[13px] font-medium hover:bg-secondary"
          >
            현재 비중으로 되돌리기
          </button>
          <button
            type="button"
            onClick={() => {
              const each = Math.floor(10000 / rows.length);
              const rest = 10000 - each * rows.length;
              setTargets((prev) => ({
                ...prev,
                [dimension]: Object.fromEntries(
                  rows.map((r, i) => [r.key, ((each + (i === 0 ? rest : 0)) / 100).toFixed(2)]),
                ),
              }));
            }}
            className="h-9 rounded-full border px-3.5 text-[13px] font-medium hover:bg-secondary"
          >
            균등 배분
          </button>
        </div>

        <Field label="추가 투입 현금" hint="0이면 현재 평가금액 안에서만 조정합니다.">
          <DecimalInput
            value={cash}
            onChange={setCash}
            suffix={currency}
            ariaLabel="추가 투입 현금"
          />
        </Field>

        <SubmitButton pending={mutation.isPending}>조정 금액 계산</SubmitButton>
        {!sumOk && !invalid && (
          <p className="text-[13px] text-subtle">
            목표 비중 합계가 100.00%여야 계산할 수 있습니다.
          </p>
        )}
        <SimulationError error={mutation.error} />
      </form>

      <div className="min-w-0">
        {mutation.data && mutation.data.dimension === dimension ? (
          <div className="space-y-4">
            <RebalanceResultView result={mutation.data} currency={currency} />
            <SaveSimulation type="rebalance" input={mutation.variables} result={mutation.data} />
          </div>
        ) : (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-subtle">
            목표 비중을 입력하고 계산하면 항목별 가상 조정 금액이 여기에 표시됩니다.
          </p>
        )}
      </div>
    </div>
  );
}
