"use client";

import useSWR from "swr";
import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, FallbackStats, fetchOverrideStatus } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function FallbackStatsCard() {
  const { data, isLoading, error } = usePolling<FallbackStats>(
    metricsPaths.fallbackStats("today"),
    30000
  );
  const { data: override } = useSWR("override-status", fetchOverrideStatus, {
    refreshInterval: 60_000,
  });
  const overrideActive = override?.is_active === true;

  const triggeredCount = data?.triggered_count ?? 0;
  const codes = data?.codes ?? [];
  const hasFallback = triggeredCount > 0;

  return (
    <Card
      className={cn(
        "transition-colors",
        hasFallback
          ? "border-amber-500/60 bg-amber-950/10"
          : "border-border",
        overrideActive && "opacity-50"
      )}
    >
      <CardHeader>
        {overrideActive && (
          <p className="mb-2 rounded bg-amber-500/10 px-2 py-1 text-xs text-amber-900 dark:text-amber-200">
            ⚠️ 현재 자동 롤백 중 — 폴백 일시 비활성 (과거 통계 참조용)
          </p>
        )}
        <CardTitle className="flex items-center gap-2">
          폴백 발동 통계
          {hasFallback && (
            <span className="text-amber-400 text-sm">⚠️</span>
          )}
        </CardTitle>
        <CardDescription>
          풀 하한 폴백 발동 횟수 · 오늘 기준 · 30초 갱신
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <div className="space-y-3">
            {/* 발동 횟수 */}
            <div className="flex items-baseline gap-2">
              <span
                className={cn(
                  "font-mono text-3xl font-bold tabular-nums",
                  hasFallback ? "text-amber-400" : "text-muted-foreground"
                )}
              >
                {triggeredCount}
              </span>
              <span className="text-xs font-mono text-muted-foreground">
                회 발동
              </span>
            </div>

            {/* 종목 배지 목록 */}
            {codes.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {codes.map((code) => (
                  <Badge
                    key={code}
                    variant="outline"
                    className="text-[10px] font-mono px-1.5 py-0 border-amber-500/50 text-amber-400 bg-amber-500/10"
                  >
                    ⚠️ {code}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs font-mono text-muted-foreground">
                {hasFallback ? "종목 정보 없음" : "폴백 발동 없음"}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
