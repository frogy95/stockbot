import { ScoreHistogramCard } from "@/components/diagnostics/score-histogram-card";
import { StageHeatmapCard } from "@/components/diagnostics/stage-heatmap-card";
import { TopRejectsCard } from "@/components/diagnostics/top-rejects-card";
import { FallbackStatsCard } from "@/components/diagnostics/fallback-stats-card";
import { ShadowHeatmapCard } from "@/components/diagnostics/shadow-heatmap-card";
import { OverrideBanner } from "@/components/diagnostics/override-banner";
import { FallbackSignalRateCard } from "@/components/diagnostics/fallback-signal-rate-card";
import { AutoRollbackMultiTrigger } from "@/components/diagnostics/auto-rollback-multi-trigger";
import { TierCorrelationCard } from "@/components/diagnostics/tier-correlation-card";
import { TierPassRateCard } from "@/components/diagnostics/tier-pass-rate-card";
import { VolumeSurgeCard } from "@/components/diagnostics/volume-surge-card";
import { TimeFilterCard } from "@/components/diagnostics/time-filter-card";

export default function DiagnosticsPage() {
  return (
    <div className="space-y-6 p-6">
      <OverrideBanner />
      <header className="space-y-1">
        <h1 className="text-lg font-mono font-semibold tracking-wide">
          신호 진단 (Phase 8.5 / 8.6)
        </h1>
        <p className="text-xs font-mono text-muted-foreground">
          폴백 신호율(M-F2) · 자동 롤백 다중 트리거(R1~R4 + G3) ·
          2차 스크리닝 점수 분포 · 전략 stage heatmap · 실시간 reject 추이 ·
          Shadow 필터 평가 · 폴백 발동 통계
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <FallbackSignalRateCard />
        <AutoRollbackMultiTrigger />
        <TierCorrelationCard />
        <TierPassRateCard />
        <VolumeSurgeCard />
        <TimeFilterCard />
        <ScoreHistogramCard />
        <StageHeatmapCard />
        <TopRejectsCard />
        <FallbackStatsCard />
        <ShadowHeatmapCard />
      </div>
    </div>
  );
}
