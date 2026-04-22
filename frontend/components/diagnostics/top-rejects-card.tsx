"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, TopRejectsResponse } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatTimeHMS } from "@/lib/format";

function pctGap(breakoutRef: number | null, currentPrice: number | null): string {
  if (!breakoutRef || !currentPrice) return "—";
  const pct = ((currentPrice - breakoutRef) / breakoutRef) * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export function TopRejectsCard() {
  const { data, isLoading, error } = usePolling<TopRejectsResponse>(
    metricsPaths.topRejects(5),
    5000
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>탈락 상위 종목 (실시간)</CardTitle>
        <CardDescription>5초 폴링 · 최근 reject 이벤트 5건</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (data?.items?.length ?? 0) === 0 ? (
          <p className="text-xs font-mono text-muted-foreground">
            수집된 reject 이벤트가 없습니다.
          </p>
        ) : (
          <ul className="space-y-1.5 font-mono text-[11px]">
            {data!.items.map((item, idx) => (
              <li
                key={idx}
                className="flex items-center gap-2 border border-border/30 rounded px-2 py-1"
              >
                <span className="text-muted-foreground w-14 shrink-0">
                  {item.recorded_at ? formatTimeHMS(item.recorded_at) : "—"}
                </span>
                <span className="w-16 text-foreground">
                  {item.stock_code ?? "—"}
                </span>
                <span className="flex-1 truncate text-red-500">{item.stage}</span>
                <span className="w-20 text-right tabular-nums">
                  {pctGap(item.breakout_ref, item.current_price)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
