import { ScoreHistogramCard } from "@/components/diagnostics/score-histogram-card";
import { StageHeatmapCard } from "@/components/diagnostics/stage-heatmap-card";
import { TopRejectsCard } from "@/components/diagnostics/top-rejects-card";
import { FallbackStatsCard } from "@/components/diagnostics/fallback-stats-card";
import { ShadowHeatmapCard } from "@/components/diagnostics/shadow-heatmap-card";

export default function DiagnosticsPage() {
  return (
    <div className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-mono font-semibold tracking-wide">
          신호 진단 (Phase 8.5)
        </h1>
        <p className="text-xs font-mono text-muted-foreground">
          2차 스크리닝 점수 분포 · 전략 stage heatmap · 실시간 reject 추이 ·
          Shadow 필터 평가 · 폴백 발동 통계(Sprint 2)
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <ScoreHistogramCard />
        <StageHeatmapCard />
        <TopRejectsCard />
        <FallbackStatsCard />
        <ShadowHeatmapCard />
      </div>
    </div>
  );
}
