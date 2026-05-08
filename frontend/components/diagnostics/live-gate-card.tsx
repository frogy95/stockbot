"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LiveGateStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const GATE_LABELS: Record<string, string> = {
  g_bt1: "G-Bt1: KS p-value ≥ 0.05",
  g_bt2: "G-Bt2: 시뮬-실측 절대차 < 임계",
  g_bt3: "G-Bt3: Bootstrap CI 포함 검사",
};

interface Props {
  status: LiveGateStatus;
}

export function LiveGateCard({ status }: Props) {
  const [showDetails, setShowDetails] = useState(false);

  const gates = [
    { key: "g_bt1", passed: status.g_bt1_passed },
    { key: "g_bt2", passed: status.g_bt2_passed },
    { key: "g_bt3", passed: status.g_bt3_passed },
  ];

  const hasDetails =
    status.details !== null &&
    Object.keys(status.details).length > 0;

  return (
    <Card
      className={cn(
        "transition-colors",
        !status.all_passed && status.evaluated_at !== null
          ? "border-red-500/60"
          : status.all_passed
          ? "border-emerald-500/40"
          : "border-border"
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-mono text-sm">
          LIVE 토글 게이트
          {status.all_passed ? (
            <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-mono text-emerald-300">
              ALL PASS
            </span>
          ) : status.evaluated_at !== null ? (
            <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-mono text-red-300">
              BLOCKED
            </span>
          ) : null}
        </CardTitle>
        <CardDescription className="font-mono text-[11px]">
          Walk-forward 백테스트 게이트 · G-Bt1~G-Bt3 통과 필요
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* 미평가 배너 */}
          {status.evaluated_at === null && (
            <div className="rounded bg-muted/30 px-3 py-2 text-[11px] font-mono text-muted-foreground">
              아직 평가되지 않음 — 백테스트 실행 후 자동 갱신
            </div>
          )}

          {/* 차단 배너 */}
          {!status.all_passed && status.evaluated_at !== null && (
            <div className="rounded border border-red-500/40 bg-red-950/20 px-3 py-2 text-[11px] font-mono text-red-300">
              dry_run 강제 유지 — LIVE 토글 차단
            </div>
          )}

          {/* ALL PASS 배너 */}
          {status.all_passed && (
            <div className="rounded border border-emerald-500/40 bg-emerald-950/20 px-3 py-2 text-[11px] font-mono text-emerald-300">
              모든 게이트 통과 — LIVE 전환 허용
            </div>
          )}

          {/* 게이트 목록 */}
          <ul className="space-y-2">
            {gates.map(({ key, passed }) => (
              <li key={key} className="flex items-center gap-3">
                <span
                  className={cn(
                    "text-base leading-none",
                    passed ? "text-emerald-400" : "text-red-400"
                  )}
                  aria-label={passed ? "통과" : "실패"}
                >
                  {passed ? "✅" : "❌"}
                </span>
                <span
                  className={cn(
                    "text-[11px] font-mono",
                    passed ? "text-foreground" : "text-red-300"
                  )}
                >
                  {GATE_LABELS[key] ?? key}
                </span>
              </li>
            ))}
          </ul>

          {/* 평가 시각 */}
          {status.evaluated_at !== null && (
            <p className="text-[10px] font-mono text-muted-foreground">
              평가 시각: {new Date(status.evaluated_at).toLocaleString("ko-KR")}
            </p>
          )}

          {/* 상세 토글 */}
          {hasDetails && (
            <div>
              <button
                type="button"
                onClick={() => setShowDetails((v) => !v)}
                className="text-[11px] font-mono text-sky-400 underline-offset-2 hover:underline focus:outline-none"
              >
                {showDetails ? "상세 숨기기 ▲" : "상세 보기 ▼"}
              </button>
              {showDetails && (
                <pre className="mt-2 overflow-x-auto rounded bg-muted/30 p-2 text-[10px] font-mono text-muted-foreground">
                  {JSON.stringify(status.details, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
