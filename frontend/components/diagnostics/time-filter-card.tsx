"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TimeFilterStatsResponse, metricsPaths } from "@/lib/api";
import { usePolling } from "@/lib/hooks/use-polling";
import { cn } from "@/lib/utils";

/**
 * Phase 8.6 Sprint 3 — 시간대별 time_filter 차단 횟수 카드.
 *
 * - morning_lockout / afternoon_lockout / gap_open_morning_exception 3종 표시
 * - Redis 키 부재 시 0 반환 (키 적재는 Task 6에서 통합 예정)
 */
export function TimeFilterCard() {
  const { data, isLoading, error } = usePolling<TimeFilterStatsResponse>(
    metricsPaths.timeFilterStats(),
    60_000,
  );

  const maxCount = Math.max(
    1,
    data?.morning_lockout ?? 0,
    data?.afternoon_lockout ?? 0,
    data?.gap_open_morning_exception ?? 0,
  );

  const totalBlocked =
    (data?.morning_lockout ?? 0) + (data?.afternoon_lockout ?? 0);

  return (
    <Card className="transition-colors border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          time_filter 차단 현황
          {data && totalBlocked > 20 && (
            <span className="text-amber-500 text-sm" aria-label="warn">
              ⚠
            </span>
          )}
        </CardTitle>
        <CardDescription>
          시간대별 진입 차단 횟수 · morning/afternoon lockout + gap 예외 · 60초 갱신
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

            {/* 시간대별 차단 횟수 */}
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">시간대별 차단 횟수</p>
              <div className="space-y-1 text-[11px] font-mono">
                <FilterRow
                  label="morning"
                  value={data.morning_lockout}
                  max={maxCount}
                  color="bg-orange-500/60"
                  tooltip="09:00–09:10 진입 차단"
                />
                <FilterRow
                  label="afternoon"
                  value={data.afternoon_lockout}
                  max={maxCount}
                  color="bg-purple-500/60"
                  tooltip="14:30 이후 진입 차단"
                />
                <FilterRow
                  label="gap_exc"
                  value={data.gap_open_morning_exception}
                  max={maxCount}
                  color="bg-emerald-500/60"
                  tooltip="09:00–09:05 gap_open tier 예외 통과"
                />
              </div>
            </div>

            {/* 요약 */}
            <div className="rounded bg-muted/30 px-3 py-2 text-[11px] font-mono">
              <span className="text-muted-foreground">총 차단: </span>
              <span
                className={cn(
                  "tabular-nums",
                  totalBlocked > 20 ? "text-amber-300" : "text-muted-foreground",
                )}
              >
                {totalBlocked}
              </span>
              <span className="ml-2 text-muted-foreground">건</span>
              <span className="ml-3 text-muted-foreground">gap 예외: </span>
              <span className="tabular-nums text-emerald-400">
                {data.gap_open_morning_exception}
              </span>
              <span className="text-muted-foreground">건</span>
            </div>

            {/* 키 적재 안내 */}
            <p className="text-[10px] font-mono text-muted-foreground opacity-60">
              * Redis 카운터 적재는 Task 6(통합 회귀) 후 활성화 예정 — 현재 0 표시 가능
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FilterRow({
  label,
  value,
  max,
  color,
  tooltip,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
  tooltip?: string;
}) {
  const widthPct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2" title={tooltip}>
      <span className="w-16 shrink-0 text-muted-foreground">{label}</span>
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
