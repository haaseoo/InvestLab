"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { ASSET_CLASS_COLORS, FALLBACK_CHART_COLOR } from "@/lib/chart";
import { formatMoney, formatPercent } from "@/lib/format";
import type { AllocationSlice } from "@/types/portfolio";

interface ChartDatum {
  key: string;
  label: string;
  value: number;
  slice: AllocationSlice;
}

function ChartTooltip({
  active,
  payload,
  currency,
}: {
  active?: boolean;
  payload?: readonly { payload: ChartDatum }[];
  currency: string;
}) {
  const datum = payload?.[0]?.payload;
  if (!active || !datum) return null;
  return (
    <div className="rounded-xl border bg-card px-3 py-2 text-[13px] shadow-card">
      <p className="font-semibold">{datum.label}</p>
      <p className="num text-subtle">
        {formatMoney(datum.slice.market_value, currency)} · {formatPercent(datum.slice.weight_pct)}
      </p>
    </div>
  );
}

const assetClassColor = (slice: AllocationSlice) =>
  ASSET_CLASS_COLORS[slice.key] ?? FALLBACK_CHART_COLOR;

interface AssetAllocationChartProps {
  slices: AllocationSlice[];
  currency: string;
  /** 조각 색. 기본은 자산군별 고정색이다. */
  colorOf?: (slice: AllocationSlice) => string;
  /** 도넛 가운데 값 */
  centerLabel: string;
  centerValue: string;
}

export function AssetAllocationChart({
  slices,
  currency,
  centerLabel,
  centerValue,
  colorOf = assetClassColor,
}: AssetAllocationChartProps) {
  const data: ChartDatum[] = slices.map((slice) => ({
    key: slice.key,
    label: slice.label,
    value: Number(slice.market_value),
    slice,
  }));

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="relative mx-auto aspect-square w-full max-w-[220px]">
        <ResponsiveContainer
          width="100%"
          height="100%"
          initialDimension={{ width: 320, height: 240 }}
        >
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="label"
              innerRadius="72%"
              outerRadius="100%"
              startAngle={90}
              endAngle={-270}
              stroke="var(--card)"
              strokeWidth={2}
              cornerRadius={4}
              isAnimationActive={false}
            >
              {data.map(({ key, slice }) => (
                <Cell key={key} fill={colorOf(slice)} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip currency={currency} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-xs text-subtle">{centerLabel}</span>
          <span className="text-[15px] font-bold num tracking-tight">{centerValue}</span>
        </div>
      </div>

      <ul className="space-y-2.5">
        {slices.map((slice) => (
          <li key={slice.key} className="flex items-center gap-2.5 text-sm">
            <span
              className="size-2.5 shrink-0 rounded-full"
              style={{ background: colorOf(slice) }}
              aria-hidden="true"
            />
            <span className="min-w-0 flex-1 truncate text-subtle">{slice.label}</span>
            <span className="font-semibold num">{formatPercent(slice.weight_pct)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
