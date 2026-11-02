/** 표시 전용 포맷터. 금융 계산은 서버에서 끝나며 여기서는 숫자를 만들지 않는다. */

export const MISSING = "–";

const krw = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
const usd = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const quantity = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 6 });
const percent = new Intl.NumberFormat("ko-KR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const dateTime = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const shortDate = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  month: "numeric",
  day: "numeric",
});

export function formatMoney(value: string | null, currency: string): string {
  if (value === null) return MISSING;
  const n = Number(value);
  if (currency === "KRW") return `${krw.format(n)}원`;
  if (currency === "USD") return `${n < 0 ? "-" : ""}$${usd.format(Math.abs(n))}`;
  return `${usd.format(n)} ${currency}`;
}

/** 부호를 항상 표시한다. 색상과 별개로 상승·하락을 읽을 수 있어야 한다. */
export function formatSignedMoney(value: string | null, currency: string): string {
  if (value === null) return MISSING;
  return `${Number(value) > 0 ? "+" : ""}${formatMoney(value, currency)}`;
}

export function formatPercent(value: string | null): string {
  return value === null ? MISSING : `${percent.format(Number(value))}%`;
}

export function formatSignedPercent(value: string | null): string {
  if (value === null) return MISSING;
  return `${Number(value) > 0 ? "+" : ""}${percent.format(Number(value))}%`;
}

export function formatQuantity(value: string): string {
  return quantity.format(Number(value));
}

export function formatDateTime(value: string | null): string {
  if (value === null) return MISSING;
  return `${dateTime.format(new Date(value))} KST`;
}

export function formatShortDate(value: string): string {
  return shortDate.format(new Date(value));
}

/** 차트 축 전용 축약 표기 */
export function formatKrwCompact(n: number): string {
  if (Math.abs(n) >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억`;
  if (Math.abs(n) >= 10_000) return `${Math.round(n / 10_000).toLocaleString("ko-KR")}만`;
  return n.toLocaleString("ko-KR");
}

export type Direction = "up" | "down" | "flat" | "unknown";

export function directionOf(value: string | null): Direction {
  if (value === null) return "unknown";
  const n = Number(value);
  return n > 0 ? "up" : n < 0 ? "down" : "flat";
}
