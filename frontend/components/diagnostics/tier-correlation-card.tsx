"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TierCorrelationResponse, metricsPaths } from "@/lib/api";
import { usePolling } from "@/lib/hooks/use-polling";
import { cn } from "@/lib/utils";

const TIERS = ["gap_open", "prev_high", "prev_close"] as const;

function phiColor(value: number, threshold: number) {
  const abs = Math.abs(value);
  if (abs <= threshold) return "text-emerald-400";
  if (abs <= threshold * 1.5) return "text-amber-400";
  return "text-red-400";
}

export function TierCorrelationCard() {
  const { data, isLoading, error } = usePolling<TierCorrelationResponse>(
    metricsPaths.tierCorrelation(7),
    60000,
  );

  return (
    <Card
      className={cn(
        "transition-colors",
        data && !data.ok ? "border-amber-500/60 bg-amber-950/10" : "border-border",
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          tier 상관 (phi + 조건부 P(B|A))
          {data && !data.ok && (
            <span className="text-amber-500 text-sm" aria-label="warn">
              ⚠
            </span>
          )}
        </CardTitle>
        <CardDescription>
          7일 윈도우 · phi ≤ {data?.phi_threshold ?? 0.3} · cond ≤{" "}
          {data?.cond_threshold ?? 0.5} · 60초 갱신
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading || !data ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-muted-foreground mb-2">phi 매트릭스</p>
              <div className="grid grid-cols-3 gap-2 font-mono text-xs">
                {TIERS.map((row) =>
                  TIERS.map((col) => {
                    if (row === col) {
                      return (
                        <span
                          key={`${row}-${col}`}
                          className="rounded bg-muted/40 px-2 py-1 text-center text-muted-foreground"
                        >
                          —
                        </span>
                      );
                    }
                    const key1 = `${row}-${col}`;
                    const key2 = `${col}-${row}`;
                    const value = data.phi[key1] ?? data.phi[key2] ?? 0;
                    return (
                      <span
                        key={`${row}-${col}`}
                        className={cn(
                          "rounded bg-muted/40 px-2 py-1 text-center tabular-nums",
                          phiColor(value, data.phi_threshold),
                        )}
                      >
                        {value.toFixed(3)}
                      </span>
                    );
                  }),
                )}
              </div>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-2">조건부 P(B|A)</p>
              <ul className="grid grid-cols-2 gap-1 text-xs font-mono">
                {Object.entries(data.cond_prob).map(([key, value]) => (
                  <li
                    key={key}
                    className="flex items-center justify-between rounded bg-muted/40 px-2 py-1"
                  >
                    <span className="text-muted-foreground">{key}</span>
                    <span
                      className={cn(
                        "tabular-nums",
                        value <= data.cond_threshold
                          ? "text-emerald-400"
                          : "text-amber-400",
                      )}
                    >
                      {value.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="text-xs font-mono text-muted-foreground">
              max phi {data.max_phi.toFixed(3)} · max cond {data.max_cond.toFixed(2)}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
