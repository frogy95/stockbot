"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  SimVsRealDiffResponse,
  TierPassRateResponse,
  metricsPaths,
} from "@/lib/api";
import { usePolling } from "@/lib/hooks/use-polling";
import { cn } from "@/lib/utils";

const TIER_DIVERSITY_TARGET = 3;
const TIER_DIVERSITY_WINDOW = 5;

export function TierPassRateCard() {
  const { data: passRate, isLoading: prLoading, error: prError } =
    usePolling<TierPassRateResponse>(metricsPaths.tierPassRate(7), 60000);
  const { data: diff, isLoading: dLoading, error: dError } =
    usePolling<SimVsRealDiffResponse>(metricsPaths.simVsRealDiff(7), 60000);

  // tier 다양성 — 최근 5일 동안 활성 tier 종류 ≥3
  const recentBuckets = passRate?.buckets.slice(-TIER_DIVERSITY_WINDOW) ?? [];
  const activeTiersInWindow = new Set<string>();
  recentBuckets.forEach((b) => {
    if (b.gap_open > 0) activeTiersInWindow.add("gap_open");
    if (b.prev_high > 0) activeTiersInWindow.add("prev_high");
    if (b.prev_close > 0) activeTiersInWindow.add("prev_close");
  });
  const diversityOk = activeTiersInWindow.size >= TIER_DIVERSITY_TARGET;

  const maxBar = Math.max(
    1,
    ...(passRate?.buckets.flatMap((b) => [b.gap_open, b.prev_high, b.prev_close]) ?? []),
  );

  return (
    <Card
      className={cn(
        "transition-colors",
        diff && !diff.ok ? "border-red-500/70 bg-red-950/20" : "border-border",
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          tier pass rate · 시뮬-실측 절대차
          {diff && !diff.ok && (
            <span className="text-red-500 text-sm" aria-label="critical">
              🚨
            </span>
          )}
        </CardTitle>
        <CardDescription>
          tier별 일별 shadow 통과 + 시뮬↔실측 절대차 추세 · 60초 갱신
        </CardDescription>
      </CardHeader>
      <CardContent>
        {prError || dError ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : prLoading || dLoading || !passRate || !diff ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-muted-foreground mb-2">
                일별 shadow tier pass (gap_open / prev_high / prev_close)
              </p>
              <ul className="space-y-1 text-[11px] font-mono">
                {passRate.buckets.map((b) => (
                  <li key={b.date} className="flex items-center gap-2">
                    <span className="w-20 shrink-0 text-muted-foreground">
                      {b.date.slice(5)}
                    </span>
                    <Bar
                      label="gap"
                      value={b.gap_open}
                      max={maxBar}
                      color="bg-orange-500/70"
                    />
                    <Bar
                      label="ph"
                      value={b.prev_high}
                      max={maxBar}
                      color="bg-emerald-500/70"
                    />
                    <Bar
                      label="pc"
                      value={b.prev_close}
                      max={maxBar}
                      color="bg-sky-500/70"
                    />
                  </li>
                ))}
              </ul>
              <p
                className={cn(
                  "mt-2 text-xs font-mono",
                  diversityOk ? "text-emerald-400" : "text-amber-400",
                )}
              >
                {TIER_DIVERSITY_WINDOW}일 활성 tier 종류: {activeTiersInWindow.size}
                /3 {diversityOk ? "✓" : "(R3 위험)"}
              </p>
            </div>

            <div>
              <p className="text-xs text-muted-foreground mb-2">
                시뮬-실측 절대차 (임계 {diff.threshold})
              </p>
              <ul className="space-y-1 text-[11px] font-mono">
                {diff.buckets.map((b) => (
                  <li key={b.date} className="flex items-center gap-2">
                    <span className="w-20 shrink-0 text-muted-foreground">
                      {b.date.slice(5)}
                    </span>
                    <span
                      className={cn(
                        "flex-1 rounded px-2 py-0.5 tabular-nums",
                        b.diff >= diff.threshold
                          ? "bg-red-950/40 text-red-300"
                          : "bg-muted/40 text-muted-foreground",
                      )}
                    >
                      {b.diff.toFixed(3)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Bar({
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
    <div className="flex flex-1 items-center gap-1">
      <span className="w-6 shrink-0 text-muted-foreground">{label}</span>
      <div className="flex-1 h-3 rounded bg-muted/30 overflow-hidden">
        <div
          className={cn("h-full transition-all", color)}
          style={{ width: `${widthPct}%` }}
        />
      </div>
      <span className="w-7 shrink-0 text-right tabular-nums">{value}</span>
    </div>
  );
}
