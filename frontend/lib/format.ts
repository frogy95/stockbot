export function formatKRW(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(2)}억`;
  }
  if (abs >= 10_000) {
    return `${(value / 10_000).toFixed(1)}만`;
  }
  return value.toLocaleString("ko-KR") + "원";
}

export function formatRate(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}
