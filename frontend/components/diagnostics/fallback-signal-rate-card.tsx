"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, FallbackSignalRate } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const R4_THRESHOLD = 0.7;

export function FallbackSignalRateCard() {
  const { data, isLoading, error } = usePolling<FallbackSignalRate>(
    metricsPaths.fallbackSignalRate("today"),
    60000
  );

  const rate = data?.rate ?? null;
  const ratePct = rate === null ? null : Math.round(rate * 100);
  const isCritical = rate !== null && rate >= R4_THRESHOLD;

  return (
    <Card
      className={cn(
        "transition-colors",
        isCritical
          ? "border-red-500/70 bg-red-950/20"
          : ratePct !== null && ratePct >= 50
            ? "border-amber-500/60 bg-amber-950/10"
            : "border-border"
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          폴백 신호율 (M-F2)
          {isCritical && <span className="text-red-500 text-sm">🚨</span>}
        </CardTitle>
        <CardDescription>
          폴백 신호 / 폴백 발동 종목 · R4 임계 70% · 60초 갱신
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <div className="space-y-3">
            <div className="flex items-baseline gap-2">
              <span
                className={cn(
                  "font-mono text-3xl font-bold tabular-nums",
                  isCritical
                    ? "text-red-400"
                    : ratePct !== null && ratePct >= 50
                      ? "text-amber-400"
                      : "text-muted-foreground"
                )}
              >
                {ratePct === null ? "—" : `${ratePct}%`}
              </span>
              {ratePct !== null && (
                <span className="text-xs font-mono text-muted-foreground">
                  / {Math.round(R4_THRESHOLD * 100)}% 임계
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div>
                <p className="text-muted-foreground">폴백 신호 수</p>
                <p className="text-base tabular-nums">
                  {data?.fallback_signals ?? 0}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">폴백 발동 종목수</p>
                <p className="text-base tabular-nums">
                  {data?.fallback_triggered_codes ?? 0}
                </p>
              </div>
            </div>

            {rate === null && (
              <p className="text-[11px] font-mono text-muted-foreground">
                폴백 미발동 — 비율 계산 불가 (분모=0 fail-safe)
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
