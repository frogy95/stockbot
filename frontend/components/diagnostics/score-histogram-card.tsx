"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, ScoreHistogramResponse } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const BUCKET_ORDER = [
  "0-10",
  "10-20",
  "20-30",
  "30-40",
  "40-50",
  "50-60",
  "60-70",
  "70-80",
  "80-90",
  "90-100",
  ">=75",
];

export function ScoreHistogramCard() {
  const { data, isLoading, error } = usePolling<ScoreHistogramResponse>(
    metricsPaths.scoreHistogram(7),
    30000
  );

  const maxCount = Math.max(
    1,
    ...(data?.buckets.flatMap((b) => [b.count_today, b.count_7d_avg]) ?? [0])
  );

  const byBucket = new Map(data?.buckets.map((b) => [b.bucket, b]) ?? []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>2차 스크리닝 점수 분포</CardTitle>
        <CardDescription>
          오늘(빨강) vs 최근 7일 평균(회색) — pass_threshold=75
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <div className="space-y-1.5 font-mono">
            {BUCKET_ORDER.map((bucket) => {
              const row = byBucket.get(bucket);
              const today = row?.count_today ?? 0;
              const avg = row?.count_7d_avg ?? 0;
              const highlight = bucket === ">=75";
              return (
                <div key={bucket} className="flex items-center gap-2 text-[11px]">
                  <span
                    className={
                      "w-16 shrink-0 text-right " +
                      (highlight ? "text-red-500 font-semibold" : "text-muted-foreground")
                    }
                  >
                    {bucket}
                  </span>
                  <div className="flex-1 relative h-4 rounded bg-muted/40 overflow-hidden">
                    <div
                      className="absolute inset-y-0 left-0 bg-muted-foreground/40"
                      style={{ width: `${(avg / maxCount) * 100}%` }}
                    />
                    <div
                      className={
                        "absolute inset-y-0 left-0 " +
                        (highlight ? "bg-red-500/80" : "bg-red-400/70")
                      }
                      style={{ width: `${(today / maxCount) * 100}%` }}
                    />
                  </div>
                  <span className="w-14 text-right tabular-nums">
                    {today}
                  </span>
                  <span className="w-14 text-right tabular-nums text-muted-foreground">
                    {avg.toFixed(1)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
