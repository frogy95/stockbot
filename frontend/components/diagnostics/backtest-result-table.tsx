"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { BacktestRunDetail, TierMetric } from "@/lib/api";
import { cn } from "@/lib/utils";

const TIER_LABELS: Record<string, string> = {
  gap_open: "gap_open",
  prev_high: "prev_high",
  prev_close: "prev_close",
  volume_surge: "volume_surge",
};

function pvalueColor(p: number | null): string {
  if (p === null) return "text-muted-foreground";
  if (p < 0.05) return "text-red-400";
  if (p < 0.1) return "text-amber-400";
  return "text-emerald-400";
}

function diffColor(sim: number, actual: number | null): string {
  if (actual === null) return "text-muted-foreground";
  const gap = Math.abs(sim - actual);
  if (gap > 0.15) return "text-red-400";
  if (gap > 0.08) return "text-amber-400";
  return "text-emerald-400";
}

function fmtPct(v: number | null): string {
  if (v === null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtNum(v: number | null, digits = 3): string {
  if (v === null) return "—";
  return v.toFixed(digits);
}

interface Props {
  run: BacktestRunDetail;
}

export function BacktestResultTable({ run }: Props) {
  const tierOrder = ["gap_open", "prev_high", "prev_close", "volume_surge"];
  const metricMap = new Map<string, TierMetric>(
    run.metrics.map((m) => [m.tier, m])
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-mono text-sm">
          <span>백테스트 상세 결과</span>
          <StatusBadge status={run.status} />
        </CardTitle>
        <CardDescription className="font-mono text-[11px]">
          {run.period_start} ~ {run.period_end} · {run.n_trading_days}일 ·
          박스권 {run.regime_box_days}일 / 추세 {run.regime_trend_days}일
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-border/40">
                <TableHead className="font-mono text-[11px] text-muted-foreground">
                  tier
                </TableHead>
                <TableHead className="font-mono text-[11px] text-muted-foreground text-right">
                  시뮬 pass율
                </TableHead>
                <TableHead className="font-mono text-[11px] text-muted-foreground text-right">
                  실측 pass율
                </TableHead>
                <TableHead className="font-mono text-[11px] text-muted-foreground text-right">
                  격차
                </TableHead>
                <TableHead className="font-mono text-[11px] text-muted-foreground text-right">
                  KS stat
                </TableHead>
                <TableHead className="font-mono text-[11px] text-muted-foreground text-right">
                  KS p-value
                </TableHead>
                <TableHead className="font-mono text-[11px] text-muted-foreground text-right">
                  Bootstrap CI
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tierOrder.map((tier) => {
                const m = metricMap.get(tier);
                if (!m) {
                  return (
                    <TableRow
                      key={tier}
                      className="border-border/20 text-[11px] font-mono"
                    >
                      <TableCell className="text-muted-foreground">
                        {TIER_LABELS[tier] ?? tier}
                      </TableCell>
                      <TableCell
                        colSpan={6}
                        className="text-muted-foreground text-center"
                      >
                        데이터 없음
                      </TableCell>
                    </TableRow>
                  );
                }
                const gap =
                  m.pass_rate_actual !== null
                    ? m.pass_rate_simulated - m.pass_rate_actual
                    : null;

                return (
                  <TableRow
                    key={tier}
                    className="border-border/20 text-[11px] font-mono"
                  >
                    <TableCell className="text-xs text-foreground">
                      {TIER_LABELS[tier] ?? tier}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sky-300">
                      {fmtPct(m.pass_rate_simulated)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-emerald-300">
                      {fmtPct(m.pass_rate_actual)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "text-right tabular-nums",
                        diffColor(m.pass_rate_simulated, m.pass_rate_actual)
                      )}
                    >
                      {gap !== null
                        ? `${gap >= 0 ? "+" : ""}${(gap * 100).toFixed(1)}%`
                        : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {fmtNum(m.ks_statistic)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "text-right tabular-nums font-semibold",
                        pvalueColor(m.ks_pvalue)
                      )}
                    >
                      {fmtNum(m.ks_pvalue)}
                      {m.ks_pvalue !== null && m.ks_pvalue < 0.05 && (
                        <span className="ml-1 text-red-400">*</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {m.bootstrap_ci_lower !== null &&
                      m.bootstrap_ci_upper !== null
                        ? `[${fmtNum(m.bootstrap_ci_lower, 2)}, ${fmtNum(m.bootstrap_ci_upper, 2)}]`
                        : "—"}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
        <p className="mt-2 text-[10px] font-mono text-muted-foreground">
          KS p-value &lt; 0.05 → 분포 드리프트 감지 (빨간 *). 실측 pass율 없으면
          —. Bootstrap CI: 95% 신뢰구간.
        </p>
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status: BacktestRunDetail["status"] }) {
  const variants = {
    running: "bg-sky-500/20 text-sky-300",
    completed: "bg-emerald-500/20 text-emerald-300",
    failed: "bg-red-500/20 text-red-300",
  };
  const labels = {
    running: "실행 중",
    completed: "완료",
    failed: "실패",
  };
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-mono",
        variants[status]
      )}
    >
      {labels[status]}
    </span>
  );
}
