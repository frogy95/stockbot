"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, Phase86Status } from "@/lib/api";
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

const R4_THRESHOLD = 0.7;

interface TriggerRow {
  id: "R1" | "R2" | "R3" | "R4" | "G3";
  label: string;
  desc: string;
  active: boolean;
  hint?: string;
}

export function AutoRollbackMultiTrigger() {
  const { data, isLoading, error } = usePolling<Phase86Status>(
    metricsPaths.phase86Status(),
    60000
  );

  const rollbackActive = data?.rollback_active ?? false;
  const circuitActive = data?.circuit_breaker_active ?? false;
  const r4Share = data?.fallback_share ?? null;

  // R1~R3은 발동 일자 streak 정보가 백엔드 detail에 한정 — Sprint 2에서 진행률 노출 예정.
  // 본 Sprint는 OR 종합 활성 상태(rollback_active) + R4 분자/분모 라이브 + G3 활성 상태를 표기.
  const rows: TriggerRow[] = [
    {
      id: "R1",
      label: "R1",
      desc: "신호 0건 3거래일 연속",
      active: rollbackActive,
      hint: "OR 발동 시 활성 — 개별 streak는 Sprint 2에서 시각화",
    },
    {
      id: "R2",
      label: "R2",
      desc: "폴백 발동 3거래일 연속 (v0)",
      active: rollbackActive,
      hint: "OR 발동 시 활성",
    },
    {
      id: "R3",
      label: "R3",
      desc: "tier 다양성 ≤1, 5거래일 (Sprint 2 후 활성)",
      active: false,
      hint: "AUTO_ROLLBACK_R3_ENABLED=False (기본 비활성)",
    },
    {
      id: "R4",
      label: "R4",
      desc: `폴백 비중 ≥${Math.round(R4_THRESHOLD * 100)}% 1거래일`,
      active: r4Share !== null && r4Share >= R4_THRESHOLD,
      hint:
        r4Share === null
          ? "오늘 분모=0 — 평가 보류"
          : `현재 ${Math.round(r4Share * 100)}%`,
    },
    {
      id: "G3",
      label: "G3",
      desc: "1차→2차 통과율 회로차단기",
      active: circuitActive,
      hint: circuitActive
        ? "회로차단기 활성 — 신규 진입 차단 / 청산 신호 통과"
        : "정상",
    },
  ];

  const anyActive = rows.some((r) => r.active);

  return (
    <Card
      className={cn(
        "transition-colors",
        anyActive ? "border-red-500/70 bg-red-950/15" : "border-border"
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          자동 롤백 다중 트리거
          {anyActive && <span className="text-red-500 text-sm">🚨</span>}
        </CardTitle>
        <CardDescription>
          Phase 8.6 G2(R1~R4) + G3 회로차단기 · 60초 갱신
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-destructive text-xs font-mono">로드 실패</p>
        ) : isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <ul className="space-y-2">
            {rows.map((row) => (
              <li
                key={row.id}
                className={cn(
                  "flex items-center justify-between gap-3 rounded border px-3 py-2 text-xs font-mono",
                  row.active
                    ? "border-red-500/60 bg-red-500/10"
                    : "border-border bg-transparent"
                )}
              >
                <div className="flex items-center gap-2">
                  <Badge
                    variant={row.active ? "destructive" : "outline"}
                    className="font-mono text-[10px]"
                  >
                    {row.label}
                  </Badge>
                  <span className="text-foreground">{row.desc}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  {row.hint && (
                    <span className="text-[10px]">{row.hint}</span>
                  )}
                  <span
                    className={cn(
                      "text-[10px] font-semibold",
                      row.active ? "text-red-400" : "text-emerald-500"
                    )}
                  >
                    {row.active ? "ACTIVE" : "—"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
