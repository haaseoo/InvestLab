"use client";

import {
  Area,
  ComposedChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatDateTime, formatKrwCompact, formatMoney, formatShortDate } from "@/lib/format";
import type { SnapshotPoint } from "@/types/portfolio";

interface ChartDatum {
  capturedAt: string;
  marketValue: number;
  costBasis: number;
  point: SnapshotPoint;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: readonly { payload: ChartDatum }[];
}) {
  const datum = payload?.[0]?.payload;
  if (!active || !datum) return null;
  const { point } = datum;
  return (
    <div className="rounded-xl border bg-card px-3 py-2 text-[13px] shadow-card">
      <p className="mb-1 text-subtle">{formatDateTime(point.captured_at)}</p>
      <p className="flex justify-between gap-4 num">
        <span className="text-subtle">평가자산</span>
        <span className="font-semibold">
          {formatMoney(point.total_market_value, point.valuation_currency)}
        </span>
      </p>
      <p className="flex justify-between gap-4 num">
        <span className="text-subtle">투자 원금</span>
        <span className="font-semibold">
          {formatMoney(point.total_cost_basis, point.valuation_currency)}
        </span>
      </p>
    </div>
  );
}

function Legend() {
  return (
    <ul className="mb-3 flex flex-wrap gap-4 text-[13px] text-subtle">
      <li className="flex items-center gap-2">
        <span className="h-0.5 w-4 rounded-full bg-chart-1" aria-hidden="true" />
        평가자산
      </li>
      <li className="flex items-center gap-2">
        <span className="h-0 w-4 border-t-2 border-dashed border-faint" aria-hidden="true" />
        투자 원금
      </li>
    </ul>
  );
}

export function PortfolioChart({ points }: { points: SnapshotPoint[] }) {
  const data: ChartDatum[] = points.map((point) => ({
    capturedAt: point.captured_at,
    marketValue: Number(point.total_market_value),
    costBasis: Number(point.total_cost_basis),
    point,
  }));

  return (
    <div className="flex flex-1 flex-col">
      <Legend />
      <div className="h-64 min-w-0 lg:h-auto lg:min-h-64 lg:flex-1">
        <ResponsiveContainer
          width="100%"
          height="100%"
          initialDimension={{ width: 320, height: 240 }}
        >
          <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="portfolio-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.14} />
                <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="capturedAt"
              tickFormatter={formatShortDate}
              tickLine={false}
              axisLine={false}
              minTickGap={48}
              tick={{ fontSize: 12, fill: "var(--text-subtle)" }}
            />
            <YAxis
              tickFormatter={formatKrwCompact}
              tickLine={false}
              axisLine={false}
              width={52}
              domain={["auto", "auto"]}
              tick={{ fontSize: 12, fill: "var(--text-subtle)" }}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: "var(--text-secondary)", strokeWidth: 1 }}
            />
            <Area
              type="monotone"
              dataKey="marketValue"
              stroke="var(--chart-1)"
              strokeWidth={2}
              fill="url(#portfolio-area)"
              isAnimationActive={false}
              activeDot={{ r: 4, stroke: "var(--card)", strokeWidth: 2 }}
            />
            <Line
              type="stepAfter"
              dataKey="costBasis"
              stroke="var(--text-secondary)"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={false}
              activeDot={{ r: 4, stroke: "var(--card)", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
