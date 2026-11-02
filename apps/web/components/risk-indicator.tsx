import { formatPercent, MISSING } from "@/lib/format";

interface RiskIndicatorProps {
  label: string;
  /** 0~100 범위의 비중. null이면 값을 계산할 수 없는 상태다. */
  valuePct: string | null;
  description?: string;
}

/** 비중을 게이지로 표시한다. 근거 없는 위험 등급(높음·낮음)은 붙이지 않는다. */
export function RiskIndicator({ label, valuePct, description }: RiskIndicatorProps) {
  const width = valuePct === null ? 0 : Math.min(Math.max(Number(valuePct), 0), 100);
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-lg font-bold num tracking-tight">
          {valuePct === null ? MISSING : formatPercent(valuePct)}
        </span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={valuePct === null ? undefined : width}
        className="h-1.5 rounded-full bg-secondary"
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
      </div>
      {description && <p className="text-[13px] text-subtle">{description}</p>}
    </div>
  );
}
