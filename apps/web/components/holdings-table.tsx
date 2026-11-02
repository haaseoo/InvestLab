"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, Search, SearchX } from "lucide-react";
import { useMemo, useState } from "react";

import { PnlText } from "@/components/pnl-text";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import {
  formatMoney,
  formatPercent,
  formatQuantity,
  formatSignedMoney,
  formatSignedPercent,
  MISSING,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Holding } from "@/types/portfolio";

type CurrencyView = "valuation" | "native";
type SortKey =
  | "name"
  | "symbol"
  | "market"
  | "quantity"
  | "average_cost"
  | "current_price"
  | "market_value"
  | "unrealized_pnl"
  | "unrealized_pnl_pct"
  | "weight_pct";
type Sort = { key: SortKey; direction: "asc" | "desc" };

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "name", label: "종목명" },
  { key: "symbol", label: "종목코드" },
  { key: "market", label: "시장" },
  { key: "quantity", label: "보유 수량", numeric: true },
  { key: "average_cost", label: "평균 매입단가", numeric: true },
  { key: "current_price", label: "현재가", numeric: true },
  { key: "market_value", label: "평가금액", numeric: true },
  { key: "unrealized_pnl", label: "평가손익", numeric: true },
  { key: "unrealized_pnl_pct", label: "수익률", numeric: true },
  { key: "weight_pct", label: "비중", numeric: true },
];

/**
 * 정렬 값. 금액 열은 통화가 섞이면 크기를 비교할 수 없으므로, 어떤 통화로 표시하든
 * 평가 통화 환산액 기준으로 정렬한다. 단가는 통화별로 단위가 달라 환산액 대신 같은 값으로 비교한다.
 */
function sortValue(holding: Holding, key: SortKey): string | number | null {
  switch (key) {
    case "name":
    case "symbol":
    case "market":
      return holding[key];
    case "market_value":
      return toNumber(holding.market_value_valuation);
    case "unrealized_pnl":
      return toNumber(holding.unrealized_pnl_valuation);
    default:
      return toNumber(holding[key]);
  }
}

function toNumber(value: string | null): number | null {
  return value === null ? null : Number(value);
}

function compareHoldings(a: Holding, b: Holding, { key, direction }: Sort): number {
  const left = sortValue(a, key);
  const right = sortValue(b, key);
  // 값이 없는 종목은 정렬 방향과 무관하게 맨 뒤로 보낸다.
  if (left === null) return right === null ? 0 : 1;
  if (right === null) return -1;
  const order =
    typeof left === "string" ? left.localeCompare(String(right), "ko") : left - Number(right);
  return direction === "asc" ? order : -order;
}

function amounts(holding: Holding, view: CurrencyView) {
  return view === "valuation"
    ? {
        currency: holding.valuation_currency,
        marketValue: holding.market_value_valuation,
        pnl: holding.unrealized_pnl_valuation,
      }
    : {
        currency: holding.currency,
        marketValue: holding.market_value,
        pnl: holding.unrealized_pnl,
      };
}

function UnavailableMark({ holding }: { holding: Holding }) {
  if (holding.valuation_status !== "unavailable") return null;
  return (
    <span className="mt-1 inline-flex h-5 items-center rounded-full bg-coral-soft px-2 text-[11px] font-semibold text-coral-strong">
      시세 조회 실패
    </span>
  );
}

export function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const [query, setQuery] = useState("");
  const [view, setView] = useState<CurrencyView>("valuation");
  const [sort, setSort] = useState<Sort>({ key: "market_value", direction: "desc" });

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return holdings
      .filter(
        (h) =>
          !needle ||
          h.name.toLowerCase().includes(needle) ||
          h.symbol.toLowerCase().includes(needle),
      )
      .sort((a, b) => compareHoldings(a, b, sort));
  }, [holdings, query, sort]);

  const toggleSort = (key: SortKey) => {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: COLUMNS.find((c) => c.key === key)?.numeric ? "desc" : "asc" },
    );
  };

  return (
    <div className="overflow-hidden card-surface">
      <div className="flex flex-wrap items-center gap-3 p-4 md:p-5">
        <div className="relative min-w-52 flex-1">
          <Search
            className="absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-faint"
            aria-hidden="true"
          />
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="종목명 또는 코드 검색"
            aria-label="종목명 또는 코드 검색"
            className="h-11 rounded-full border-transparent bg-secondary pl-10 text-base md:text-sm"
          />
        </div>

        <div
          role="group"
          aria-label="금액 표시 통화"
          className="inline-flex rounded-full bg-secondary p-1"
        >
          {(
            [
              ["valuation", "원화 환산"],
              ["native", "거래 통화"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={view === value}
              onClick={() => setView(value)}
              className={cn(
                "h-9 rounded-full px-3.5 text-[13px] font-semibold transition-colors",
                view === value ? "bg-card shadow-sm" : "text-subtle hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 표 머리글이 없는 모바일 카드 전용 정렬 */}
        <label className="flex w-full items-center gap-2 text-sm text-subtle md:hidden">
          정렬
          <select
            value={`${sort.key}:${sort.direction}`}
            onChange={(event) => {
              const [key, direction] = event.target.value.split(":");
              setSort({ key: key as SortKey, direction: direction as Sort["direction"] });
            }}
            className="h-11 flex-1 rounded-xl border bg-card px-3 text-base text-foreground"
          >
            <option value="market_value:desc">평가금액 높은 순</option>
            <option value="market_value:asc">평가금액 낮은 순</option>
            <option value="unrealized_pnl_pct:desc">수익률 높은 순</option>
            <option value="unrealized_pnl_pct:asc">수익률 낮은 순</option>
            <option value="weight_pct:desc">비중 높은 순</option>
            <option value="name:asc">종목명 순</option>
          </select>
        </label>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title={holdings.length === 0 ? "보유 종목이 없습니다" : "검색 결과가 없습니다"}
          description={holdings.length === 0 ? undefined : "다른 종목명이나 코드로 검색해 보세요."}
        />
      ) : (
        <>
          <div className="relative hidden overflow-x-auto md:block">
            <table className="w-full min-w-[1120px] text-sm whitespace-nowrap">
              <caption className="sr-only">
                보유 종목 목록. 열 머리글을 눌러 정렬할 수 있습니다.
              </caption>
              <thead>
                <tr className="border-y bg-secondary/50">
                  {COLUMNS.map(({ key, label, numeric }, index) => {
                    const active = sort.key === key;
                    const Icon = !active
                      ? ArrowUpDown
                      : sort.direction === "asc"
                        ? ArrowUp
                        : ArrowDown;
                    return (
                      <th
                        key={key}
                        scope="col"
                        aria-sort={
                          active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"
                        }
                        className={cn(
                          "p-0 font-medium whitespace-nowrap text-subtle",
                          index === 0 && "sticky left-0 z-10 bg-background",
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => toggleSort(key)}
                          className={cn(
                            "flex h-11 w-full items-center gap-1 px-4 text-[13px] hover:text-foreground",
                            numeric && "justify-end",
                            active && "text-foreground",
                          )}
                        >
                          {label}
                          <Icon
                            className={cn("size-3.5", !active && "text-faint/70")}
                            aria-hidden="true"
                          />
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {rows.map((holding) => {
                  const { currency, marketValue, pnl } = amounts(holding, view);
                  return (
                    <tr
                      key={`${holding.market}:${holding.symbol}`}
                      className="border-b last:border-0"
                    >
                      <th
                        scope="row"
                        className="sticky left-0 z-10 max-w-60 bg-card px-4 py-3.5 text-left font-semibold"
                      >
                        <span className="block truncate">{holding.name}</span>
                        <UnavailableMark holding={holding} />
                      </th>
                      <td className="px-4 num text-subtle">{holding.symbol}</td>
                      <td className="px-4 text-subtle">{holding.market}</td>
                      <td className="px-4 text-right num">{formatQuantity(holding.quantity)}</td>
                      <td className="px-4 text-right num">
                        {formatMoney(holding.average_cost, holding.currency)}
                      </td>
                      <td className="px-4 text-right num">
                        {formatMoney(holding.current_price, holding.currency)}
                      </td>
                      <td className="px-4 text-right font-semibold num">
                        {formatMoney(marketValue, currency)}
                      </td>
                      <td className="px-4 text-right">
                        <PnlText value={pnl} text={formatSignedMoney(pnl, currency)} />
                      </td>
                      <td className="px-4 text-right">
                        <PnlText
                          value={holding.unrealized_pnl_pct}
                          text={formatSignedPercent(holding.unrealized_pnl_pct)}
                        />
                      </td>
                      <td className="px-4 text-right num">{formatPercent(holding.weight_pct)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <ul className="border-t md:hidden">
            {rows.map((holding) => {
              const { currency, marketValue, pnl } = amounts(holding, view);
              return (
                <li
                  key={`${holding.market}:${holding.symbol}`}
                  className="border-b p-4 last:border-0"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{holding.name}</p>
                      <p className="text-[13px] num text-subtle">
                        {holding.symbol} · {holding.market}
                      </p>
                      <UnavailableMark holding={holding} />
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="font-semibold num">{formatMoney(marketValue, currency)}</p>
                      <PnlText
                        value={holding.unrealized_pnl_pct}
                        text={formatSignedPercent(holding.unrealized_pnl_pct)}
                        className="text-[13px]"
                      />
                    </div>
                  </div>
                  <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-xl bg-secondary/60 p-3 text-[13px]">
                    <Detail label="보유 수량" value={formatQuantity(holding.quantity)} />
                    <Detail label="비중" value={formatPercent(holding.weight_pct)} />
                    <Detail
                      label="평균 매입단가"
                      value={formatMoney(holding.average_cost, holding.currency)}
                    />
                    <Detail
                      label="현재가"
                      value={formatMoney(holding.current_price, holding.currency)}
                    />
                    <div className="col-span-2 flex justify-between gap-2">
                      <dt className="text-subtle">평가손익</dt>
                      <dd>
                        <PnlText value={pnl} text={formatSignedMoney(pnl, currency)} />
                      </dd>
                    </div>
                  </dl>
                </li>
              );
            })}
          </ul>
        </>
      )}

      <p className="border-t px-4 py-3 text-xs text-subtle md:px-5">
        단가는 항상 거래 통화로 표시합니다. 금액 열 정렬은 원화 환산액 기준입니다. {MISSING}는 값을
        알 수 없음을 뜻하며 0이 아닙니다.
      </p>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="col-span-2 flex justify-between gap-2 min-[360px]:col-span-1 min-[360px]:block">
      <dt className="text-subtle">{label}</dt>
      <dd className="font-medium num">{value}</dd>
    </div>
  );
}
