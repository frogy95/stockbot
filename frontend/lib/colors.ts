// 한국 증시 색상 관례: 빨강=수익/상승, 파랑=손실/하락
export const PROFIT = "#EF4444";
export const LOSS = "#3B82F6";
export const NEUTRAL = "#9CA3AF";

export const LIVE_BANNER_BG = "#DC2626";
export const LIVE_BANNER_TEXT = "#FFFFFF";
export const PAPER_BANNER_BG = "#16A34A";
export const PAPER_BANNER_TEXT = "#FFFFFF";

export function getPnlColor(value: number): string {
  if (value > 0) return PROFIT;
  if (value < 0) return LOSS;
  return NEUTRAL;
}
