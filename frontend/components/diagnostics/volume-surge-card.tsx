"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { VolumeSurgeStatsResponse, metricsPaths } from "@/lib/api";
import { usePolling } from "@/lib/hooks/use-polling";
import { cn } from "@/lib/utils";

/**
 * Phase 8.6 Sprint 3 — volume_surge 신호 dry_run 현황 카드.
 *
 * - 오늘 dry_run 신호 수 / LIVE 신호 수 / 7일 이동평균 표시
 * - VOLUME_SURGE_DRY_RUN=true 배너 (Phase 8.5 OverrideBanner 패턴 재사용)
 * - LIVE 토글 게이트 placeholder (Sprint 4 후 활성)
 */
export function VolumeSurgeCard() {
  const { data, isLoading, error } = usePolling<VolumeSurgeStatsResponse>(
    metricsPaths.volumeSurgeStats(),
    60_000,
  );

  const isDryRunMode = data ? data.real_count === 0 : true;
  const maxCount = Math.max(1, data?.dry_run_count ?? 0, data?.real_count ?? 0);

  return (
    <Card
      className={cn(
        "transition-colors",
        isDryRunMode ? "border-amber-500/40" : "border-border",
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          volume-surge 신호 (dry_run)
          {isDryRunMode && (
            <span
              className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-mono text-amber-300"
              aria-label="dry-run-mode"
            >
              VOLUME_SURGE_DRY_RUN=true
            </span>
          )}
        </CardTitle>
        <CardDescription>
          거래량 급등 전략 신호 현황 · dry_run / LIVE 카운트 · 7일 MA · 60초 갱신
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading || !data ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="space-y-4">
            {/* 날짜 */}
            <p className="text-[11px] font-mono text-muted-foreground">
              기준일: {data.date}
            </p>

            {/* 오늘 카운트 */}
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">오늘 신호 수</p>
              <div className="space-y-1 text-[11px] font-mono">
                <CountRow
                  label="dry_run"
                  value={data.dry_run_count}
                  max={maxCount}
                  color="bg-amber-500/60"
                />
                <CountRow
                  label="LIVE"
                  value={data.real_count}
                  max={maxCount}
                  color="bg-sky-500/60"
                />
              </div>
            </div>

            {/* 7일 이동평균 */}
            <div className="rounded bg-muted/30 px-3 py-2 text-[11px] font-mono">
              <span className="text-muted-foreground">7일 MA (dry_run): </span>
              <span className="tabular-nums text-amber-300">
                {data.ma7_dry_run.toFixed(2)}
              </span>
              <span className="ml-2 text-muted-foreground">건/일</span>
            </div>

            {/* LIVE 토글 게이트 placeholder */}
            <div className="rounded border border-dashed border-muted/40 px-3 py-2 text-[11px] font-mono text-muted-foreground">
              LIVE 토글 게이트 미준비 — Sprint 4 후 활성
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CountRow({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  const widthPct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 shrink-0 text-muted-foreground">{label}</span>
      <div className="flex-1 h-3 rounded bg-muted/30 overflow-hidden">
        <div
          className={cn("h-full transition-all", color)}
          style={{ width: `${widthPct}%` }}
        />
      </div>
      <span className="w-8 shrink-0 text-right tabular-nums">{value}</span>
    </div>
  );
}
