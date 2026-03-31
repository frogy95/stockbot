"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { getPnlColor } from "@/lib/colors";
import { formatKRW, formatRate } from "@/lib/format";
import { cn } from "@/lib/utils";

interface DashboardSummary {
  today_pnl: number;
  today_pnl_rate: number;
  today_trade_count: number;
  active_positions: number;
  unrealized_pnl: number;
  trading_env: string;
  engine_running: boolean;
  risk_status: Record<string, unknown>;
}

function MetricCard({
  label,
  value,
  sub,
  valueColor,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  valueColor?: string;
  accent?: string;
}) {
  return (
    <div
      className={cn(
        "relative rounded-lg border border-border/50 bg-card p-5 overflow-hidden",
        "transition-colors hover:border-border/80"
      )}
    >
      {accent && (
        <div
          className="absolute left-0 top-0 bottom-0 w-0.5 rounded-l-lg"
          style={{ backgroundColor: accent }}
        />
      )}
      <p className="text-[10px] font-mono tracking-[0.18em] text-muted-foreground uppercase mb-3">
        {label}
      </p>
      <p
        className="text-2xl font-mono font-semibold tabular-nums leading-none"
        style={valueColor ? { color: valueColor } : undefined}
      >
        {value}
      </p>
      {sub && (
        <p className="text-xs font-mono text-muted-foreground mt-1.5">{sub}</p>
      )}
    </div>
  );
}

function EngineStatus({ running }: { running: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={cn(
          "inline-block w-1.5 h-1.5 rounded-full",
          running ? "bg-green-500 animate-pulse" : "bg-zinc-600"
        )}
      />
      <span
        className={cn(
          "text-[10px] font-mono tracking-widest uppercase",
          running ? "text-green-500" : "text-zinc-500"
        )}
      >
        {running ? "엔진 가동 중" : "엔진 정지"}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = usePolling<DashboardSummary>(
    "/api/v1/dashboard/summary"
  );

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-xs font-mono text-destructive">
          ⚠ 데이터를 불러올 수 없습니다
        </p>
      </div>
    );
  }

  const pnl = data?.today_pnl ?? 0;
  const pnlColor = getPnlColor(pnl);

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">대시보드</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">
            오늘의 거래 현황
          </p>
        </div>
        {data && <EngineStatus running={data.engine_running} />}
      </div>

      {/* 4개 지표 카드 */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="오늘 손익"
          value={isLoading ? "—" : formatKRW(pnl)}
          sub={isLoading ? undefined : formatRate(data?.today_pnl_rate ?? 0)}
          valueColor={isLoading ? undefined : pnlColor}
          accent={isLoading ? undefined : pnlColor}
        />
        <MetricCard
          label="미실현 손익"
          value={isLoading ? "—" : formatKRW(data?.unrealized_pnl ?? 0)}
          sub={isLoading ? undefined : `보유 ${data?.active_positions ?? 0}종목`}
          valueColor={isLoading ? undefined : getPnlColor(data?.unrealized_pnl ?? 0)}
          accent={isLoading ? undefined : getPnlColor(data?.unrealized_pnl ?? 0)}
        />
        <MetricCard
          label="활성 포지션"
          value={isLoading ? "—" : String(data?.active_positions ?? 0)}
          sub="종목"
        />
        <MetricCard
          label="오늘 거래"
          value={isLoading ? "—" : String(data?.today_trade_count ?? 0)}
          sub="건"
        />
      </div>

      {/* 리스크 상태 */}
      {data && Object.keys(data.risk_status).length > 0 && (
        <div className="rounded-lg border border-border/50 bg-card p-4">
          <p className="text-[10px] font-mono tracking-[0.18em] text-muted-foreground uppercase mb-3">
            리스크 상태
          </p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
            {Object.entries(data.risk_status).map(([k, v]) => (
              <div key={k} className="flex justify-between items-center">
                <span className="text-xs font-mono text-muted-foreground">{k}</span>
                <span className="text-xs font-mono tabular-nums">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
