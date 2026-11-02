"use client";

import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

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
  formatSignedPercent,
  MISSING,
} from "@/lib/format";
import type { BuyRequest, BuyResult } from "@/types/analysis";
import type { Holding } from "@/types/portfolio";

const FX_SOURCE = {
  same_currency: "환율 적용 없음",
  input: "입력한 환율",
  current: "현재 환율",
  unavailable: "환율 없음",
} as const;

function diffPct(before: string | null, after: string | null) {
  if (before === null || after === null) return null;
  return String(Number(after) - Number(before));
}

function BuyResultView({
  result,
  valuationCurrency,
}: {
  result: BuyResult;
  valuationCurrency: string;
}) {
  const { before, after, purchase, currency } = result;
  const rows: [string, string, string][] = [
    ["보유 수량", formatQuantity(before.quantity), formatQuantity(after.quantity)],
    [
      "평균 매입단가",
      formatMoney(before.average_cost, currency),
      formatMoney(after.average_cost, currency),
    ],
    [
      "투자 원금",
      formatMoney(before.cost_basis, currency),
      formatMoney(after.cost_basis, currency),
    ],
    [
      `투자 원금 (${valuationCurrency})`,
      formatMoney(before.cost_basis_valuation, valuationCurrency),
      formatMoney(after.cost_basis_valuation, valuationCurrency),
    ],
    [
      `평가금액 (${valuationCurrency})`,
      formatMoney(before.market_value_valuation, valuationCurrency),
      formatMoney(after.market_value_valuation, valuationCurrency),
    ],
    ["종목 비중", formatPercent(before.weight_pct), formatPercent(after.weight_pct)],
  ];
  const changed = result.weights.filter((w) => w.key !== `${result.market}:${result.symbol}`);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[15px] font-semibold">
          {result.name} <span className="num text-subtle">({result.symbol})</span>
        </h3>
        <TheoreticalBadge />
      </div>

      <ResultTable
        caption="추가 매수 전후 비교"
        head={[
          { label: "항목" },
          { label: "매수 전", numeric: true },
          { label: "매수 후", numeric: true },
        ]}
        minWidth={420}
      >
        {rows.map(([label, b, a]) => (
          <tr key={label}>
            <th scope="row" className="text-left font-medium text-subtle">
              {label}
            </th>
            <td className="text-right num">{b}</td>
            <td className="text-right font-semibold num">{a}</td>
          </tr>
        ))}
      </ResultTable>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 rounded-xl border p-4 text-sm md:grid-cols-3">
        {[
          ["매수 수량", formatQuantity(purchase.quantity)],
          ["매수 금액", formatMoney(purchase.gross_amount, currency)],
          [
            "수수료",
            purchase.fee_amount === null ? "미적용" : formatMoney(purchase.fee_amount, currency),
          ],
          [
            "세금",
            purchase.tax_amount === null ? "미적용" : formatMoney(purchase.tax_amount, currency),
          ],
          ["총 필요 금액", formatMoney(purchase.total_cash_required, currency)],
          [
            `총 필요 금액 (${valuationCurrency})`,
            formatMoney(purchase.total_cash_required_valuation, valuationCurrency),
          ],
          [
            "적용 환율",
            purchase.fx_rate_used === null || purchase.fx_rate_source === "same_currency"
              ? FX_SOURCE[purchase.fx_rate_source]
              : `${Number(purchase.fx_rate_used).toLocaleString("ko-KR")} (${FX_SOURCE[purchase.fx_rate_source]})`,
          ],
          ...(purchase.leftover_amount !== null
            ? [["남는 금액", formatMoney(purchase.leftover_amount, currency)]]
            : []),
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-[13px] text-subtle">{label}</dt>
            <dd className="font-semibold num">{value}</dd>
          </div>
        ))}
      </dl>

      {changed.length > 0 && result.total_market_value_after !== null && (
        <ResultTable
          caption="다른 종목의 비중 변화"
          head={[
            { label: "다른 종목" },
            { label: "매수 전", numeric: true },
            { label: "매수 후", numeric: true },
            { label: "변화", numeric: true },
          ]}
          minWidth={480}
        >
          {changed.map((w) => {
            const diff = diffPct(w.before_pct, w.after_pct);
            return (
              <tr key={w.key}>
                <th scope="row" className="max-w-56 truncate text-left font-medium">
                  {w.name}
                </th>
                <td className="text-right num">{formatPercent(w.before_pct)}</td>
                <td className="text-right num">{formatPercent(w.after_pct)}</td>
                <td className="text-right">
                  <span className="num text-subtle">
                    {diff === null ? MISSING : `${formatSignedPercent(diff)}p`}
                  </span>
                </td>
              </tr>
            );
          })}
        </ResultTable>
      )}

      <p className="text-[13px] text-subtle">
        포트폴리오 평가금액 {formatMoney(result.total_market_value_before, valuationCurrency)} →{" "}
        <span className="font-semibold num text-foreground">
          {formatMoney(result.total_market_value_after, valuationCurrency)}
        </span>{" "}
        (종목 비중 변화{" "}
        <PnlText
          value={diffPct(before.weight_pct, after.weight_pct)}
          text={`${formatSignedPercent(diffPct(before.weight_pct, after.weight_pct))}p`}
        />
        )
      </p>
      <AssumptionList items={result.assumptions} />
    </div>
  );
}

export function BuySimulator({
  holdings,
  valuationCurrency,
}: {
  holdings: Holding[];
  valuationCurrency: string;
}) {
  const { source } = useSource();
  const [key, setKey] = useState(() =>
    holdings[0] ? `${holdings[0].market}:${holdings[0].symbol}` : "",
  );
  const selected = holdings.find((h) => `${h.market}:${h.symbol}` === key);
  const [mode, setMode] = useState<"quantity" | "amount">("quantity");
  const [quantity, setQuantity] = useState("1");
  const [amount, setAmount] = useState("");
  const [price, setPrice] = useState(selected?.current_price ?? "");
  const [fractional, setFractional] = useState(false);
  const [fee, setFee] = useState("");
  const [tax, setTax] = useState("");
  const [fx, setFx] = useState("");

  const mutation = useMutation({
    mutationFn: (body: BuyRequest) => api.simulateBuy(source, body),
  });

  const selectHolding = (nextKey: string) => {
    setKey(nextKey);
    const next = holdings.find((h) => `${h.market}:${h.symbol}` === nextKey);
    setPrice(next?.current_price ?? "");
    setFx("");
    mutation.reset();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    mutation.mutate({
      symbol: selected.symbol,
      market: selected.market,
      mode,
      ...(mode === "quantity" ? { quantity } : { amount }),
      price,
      allow_fractional: fractional,
      ...(fee.trim() ? { fee_amount: fee } : {}),
      ...(tax.trim() ? { tax_amount: tax } : {}),
      ...(fx.trim() ? { fx_rate: fx } : {}),
    });
  };

  const currency = selected?.currency ?? valuationCurrency;
  const foreign = currency !== valuationCurrency;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_1fr]">
      <form onSubmit={submit} className="space-y-4">
        <Field label="종목">
          <select
            value={key}
            onChange={(e) => selectHolding(e.target.value)}
            className="h-11 rounded-xl border bg-card px-3 text-base md:text-sm"
          >
            {holdings.map((h) => (
              <option key={`${h.market}:${h.symbol}`} value={`${h.market}:${h.symbol}`}>
                {h.name} ({h.symbol})
              </option>
            ))}
          </select>
        </Field>

        <Segmented
          label="매수 입력 방식"
          value={mode}
          onChange={setMode}
          options={[
            ["quantity", "수량으로"],
            ["amount", "금액으로"],
          ]}
        />

        {mode === "quantity" ? (
          <Field label="매수 수량">
            <DecimalInput
              value={quantity}
              onChange={setQuantity}
              suffix="주"
              ariaLabel="매수 수량"
            />
          </Field>
        ) : (
          <Field label="매수 금액" hint="수수료·세금 제외 금액입니다.">
            <DecimalInput
              value={amount}
              onChange={setAmount}
              suffix={currency}
              ariaLabel="매수 금액"
            />
          </Field>
        )}

        <Field
          label="가정 매수가"
          hint={`현재가 ${formatMoney(selected?.current_price ?? null, currency)}로 채워 두었습니다.`}
        >
          <DecimalInput
            value={price}
            onChange={setPrice}
            suffix={currency}
            ariaLabel="가정 매수가"
          />
        </Field>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={fractional}
            onChange={(e) => setFractional(e.target.checked)}
            className="size-4 accent-[var(--foreground)]"
          />
          소수점 수량 허용
        </label>

        <div className="grid grid-cols-2 gap-3">
          <Field label="수수료" hint="비우면 미적용">
            <DecimalInput value={fee} onChange={setFee} suffix={currency} ariaLabel="수수료" />
          </Field>
          <Field label="세금" hint="비우면 미적용">
            <DecimalInput value={tax} onChange={setTax} suffix={currency} ariaLabel="세금" />
          </Field>
        </div>

        {foreign && (
          <Field
            label={`환율 (${currency}/${valuationCurrency})`}
            hint={`비우면 현재 환율 ${selected?.fx_rate ? Number(selected.fx_rate).toLocaleString("ko-KR") : MISSING}을 씁니다.`}
          >
            <DecimalInput value={fx} onChange={setFx} ariaLabel="환율" />
          </Field>
        )}

        <SubmitButton pending={mutation.isPending}>평균단가 계산</SubmitButton>
        <SimulationError error={mutation.error} />
      </form>

      <div className="min-w-0">
        {mutation.data ? (
          <div className="space-y-4">
            <BuyResultView result={mutation.data} valuationCurrency={valuationCurrency} />
            <SaveSimulation type="buy" input={mutation.variables} result={mutation.data} />
          </div>
        ) : (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-subtle">
            종목과 수량을 입력하고 계산하면 매수 전후 평균단가, 원금, 비중 변화가 여기에 표시됩니다.
          </p>
        )}
      </div>
    </div>
  );
}
