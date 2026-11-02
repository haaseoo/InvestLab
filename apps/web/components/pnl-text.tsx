import { directionOf, MISSING } from "@/lib/format";
import { cn } from "@/lib/utils";

const META = {
  up: { glyph: "▲", label: "상승", className: "text-up" },
  down: { glyph: "▼", label: "하락", className: "text-down" },
  flat: { glyph: "", label: "변동 없음", className: "text-subtle" },
  unknown: { glyph: "", label: "알 수 없음", className: "text-subtle" },
} as const;

interface PnlTextProps {
  /** 방향을 판단할 원본 값 */
  value: string | null;
  /** 화면에 표시할 부호 포함 문자열 */
  text: string;
  className?: string;
}

/** 상승·하락을 색, 기호, 부호로 함께 나타낸다. 스크린리더에는 상승·하락을 말로 전달한다. */
export function PnlText({ value, text, className }: PnlTextProps) {
  const meta = META[directionOf(value)];
  if (value === null) return <span className={cn("num text-subtle", className)}>{MISSING}</span>;
  return (
    <span className={cn("num whitespace-nowrap", meta.className, className)}>
      {meta.glyph && (
        <span aria-hidden="true" className="mr-1 text-[0.72em]">
          {meta.glyph}
        </span>
      )}
      <span className="sr-only">{meta.label} </span>
      {text}
    </span>
  );
}
