"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, StageHeatmapResponse } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const STAGES = [
  "pass",
  "breakout",
  "min_volume_floor",
  "prev_close_time_guard",
  "volume_threshold",
  "trade_strength",
  "atr_filter",
  "confidence",
  "prev_volume_zero",
];

const HOUR_MINS: string[] = [];
for (let h = 9; h <= 15; h++) {
  for (let m = 0; m < 60; m += 10) {
    if (h === 15 && m > 30) break;
    if (h === 9 && m < 30) continue;
    HOUR_MINS.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
  }
}

function shadeFor(count: number, max: number): string {
  if (count <= 0) return "bg-muted/20";
  const ratio = Math.log1p(count) / Math.log1p(Math.max(max, 1));
  if (ratio < 0.25) return "bg-red-500/15";
  if (ratio < 0.5) return "bg-red-500/35";
  if (ratio < 0.75) return "bg-red-500/60";
  return "bg-red-500/85";
}

export function StageHeatmapCard() {
  const { data, isLoading, error } = usePolling<StageHeatmapResponse>(
    metricsPaths.stageHeatmap("today"),
    30000
  );

  const cellMap = new Map<string, number>();
  let max = 0;
  for (const cell of data?.cells ?? []) {
    cellMap.set(`${cell.stage}|${cell.hour_min}`, cell.count);
    if (cell.count > max) max = cell.count;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>전략 stage 탈락/통과 heatmap</CardTitle>
        <CardDescription>
          x=10분 단위 · y=stage · 색 농도=카운트(log) · pass는 통과, 나머지는 reject
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <div className="overflow-x-auto">
            <table className="text-[10px] font-mono border-separate border-spacing-[2px]">
              <thead>
                <tr>
                  <th className="text-right pr-2 text-muted-foreground sticky left-0 bg-card">
                    stage \ 시각
                  </th>
                  {HOUR_MINS.map((hm) => (
                    <th
                      key={hm}
                      className="text-muted-foreground font-normal w-6"
                    >
                      {hm.endsWith(":00") ? hm.slice(0, 2) : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {STAGES.map((stage) => (
                  <tr key={stage}>
                    <td className="text-right pr-2 text-muted-foreground whitespace-nowrap sticky left-0 bg-card">
                      {stage}
                    </td>
                    {HOUR_MINS.map((hm) => {
                      const count = cellMap.get(`${stage}|${hm}`) ?? 0;
                      return (
                        <td
                          key={hm}
                          title={`${stage} @ ${hm}: ${count}`}
                          className={
                            "w-4 h-4 rounded-sm " + shadeFor(count, max)
                          }
                        />
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
