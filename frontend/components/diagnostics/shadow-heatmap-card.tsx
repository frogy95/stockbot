"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, ShadowHeatmapResponse } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const HOUR_MINS: string[] = [];
for (let h = 9; h <= 15; h++) {
  for (let m = 0; m < 60; m += 10) {
    if (h === 15 && m > 30) break;
    if (h === 9 && m < 30) continue;
    HOUR_MINS.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
  }
}

function cellClass(passRate: number | null, total: number): string {
  if (total === 0) return "bg-muted/20";
  if (passRate === null) return "bg-muted/30";
  if (passRate >= 0.8) return "bg-emerald-500/75";
  if (passRate >= 0.6) return "bg-emerald-500/45";
  if (passRate >= 0.4) return "bg-yellow-500/45";
  if (passRate >= 0.2) return "bg-orange-500/55";
  return "bg-red-500/65";
}

export function ShadowHeatmapCard() {
  const { data, isLoading, error } = usePolling<ShadowHeatmapResponse>(
    metricsPaths.shadowHeatmap("today"),
    30000
  );

  const cellMap = new Map<
    string,
    { pass: number; fail: number; passRate: number | null }
  >();
  for (const cell of data?.cells ?? []) {
    cellMap.set(`${cell.stage}|${cell.hour_min}`, {
      pass: cell.pass_count,
      fail: cell.fail_count,
      passRate: cell.pass_rate,
    });
  }

  const stages = data?.stages ?? [
    "prev_close_time_guard",
    "breakout",
    "prev_volume_zero",
    "min_volume_floor",
    "volume_threshold",
    "trade_strength",
    "atr_filter",
    "confidence",
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Shadow 필터 독립 평가 (Sprint 1.5)</CardTitle>
        <CardDescription>
          각 필터를 short-circuit과 무관하게 독립 평가한 pass 비율 · 초록=높음 ·
          빨강=낮음 · 회색=표본 0 · 실제 주문 경로와 무관한 관측 데이터
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
                {stages.map((stage) => (
                  <tr key={stage}>
                    <td className="text-right pr-2 text-muted-foreground whitespace-nowrap sticky left-0 bg-card">
                      {stage}
                    </td>
                    {HOUR_MINS.map((hm) => {
                      const entry = cellMap.get(`${stage}|${hm}`);
                      const pass = entry?.pass ?? 0;
                      const fail = entry?.fail ?? 0;
                      const total = pass + fail;
                      const passRate = entry?.passRate ?? null;
                      const pct =
                        passRate === null
                          ? "표본 0"
                          : `${(passRate * 100).toFixed(0)}%`;
                      return (
                        <td
                          key={hm}
                          title={`${stage} @ ${hm}: pass=${pass} fail=${fail} (${pct})`}
                          className={
                            "w-4 h-4 rounded-sm " + cellClass(passRate, total)
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
