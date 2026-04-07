"use client";

import { useAuth } from "@/lib/auth";
import { LIVE_BANNER_BG, PAPER_BANNER_BG } from "@/lib/colors";
import { ModeIndicator } from "@/components/mode-indicator";

export function ModeBanner() {
  const { user } = useAuth();
  const isLive = user?.trading_env === "live";

  return (
    <div
      className="sticky top-0 z-50 flex items-center justify-between px-4 h-10 shrink-0 font-mono text-xs font-semibold tracking-[0.15em] uppercase text-white select-none"
      style={{ backgroundColor: isLive ? LIVE_BANNER_BG : PAPER_BANNER_BG }}
    >
      {/* 왼쪽: 매매 모드 인디케이터 */}
      <div className="flex items-center">
        <ModeIndicator />
      </div>

      {/* 가운데: 거래 환경 표시 */}
      <div className="flex items-center gap-3">
        <span
          className="inline-block w-1.5 h-1.5 rounded-full bg-white/80 animate-pulse"
          style={{ animationDuration: isLive ? "1s" : "3s" }}
        />
        {isLive ? "실전 거래 중 — LIVE TRADING" : "모의 거래 — PAPER MODE"}
        <span
          className="inline-block w-1.5 h-1.5 rounded-full bg-white/80 animate-pulse"
          style={{ animationDuration: isLive ? "1s" : "3s" }}
        />
      </div>

      {/* 오른쪽: 여백 균형 */}
      <div className="w-[var(--mode-indicator-width,64px)]" />
    </div>
  );
}
