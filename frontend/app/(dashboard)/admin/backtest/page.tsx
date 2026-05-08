"use client";

import { useState, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { BacktestResultTable } from "@/components/diagnostics/backtest-result-table";
import { KsTrendCard } from "@/components/diagnostics/ks-trend-card";
import { LiveGateCard } from "@/components/diagnostics/live-gate-card";
import {
  runBacktest,
  getBacktestRuns,
  getBacktestRun,
  getBacktestDistributionCheck,
  getLiveGateStatus,
  backfillDaily,
  BacktestRunSummary,
  BacktestRunDetail,
  KSTrendPoint,
  LiveGateStatus,
} from "@/lib/api";
import { usePolling } from "@/lib/hooks/use-polling";
import { cn } from "@/lib/utils";

// 오늘 날짜 yyyy-mm-dd
function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

// 백테스트 실행 목록 행
function RunRow({
  run,
  isSelected,
  onClick,
}: {
  run: BacktestRunSummary;
  isSelected: boolean;
  onClick: () => void;
}) {
  const statusColors = {
    running: "text-sky-400",
    completed: "text-emerald-400",
    failed: "text-red-400",
  };
  const statusLabels = { running: "실행 중", completed: "완료", failed: "실패" };

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left rounded px-3 py-2 transition-colors text-[11px] font-mono",
        isSelected
          ? "bg-sky-500/10 border border-sky-500/40"
          : "hover:bg-muted/40 border border-transparent"
      )}
    >
      <div className="flex items-center gap-3">
        <span className={cn("font-semibold", statusColors[run.status])}>
          [{statusLabels[run.status]}]
        </span>
        <span className="text-muted-foreground">
          {run.period_start} ~ {run.period_end}
        </span>
        <span className="ml-auto text-muted-foreground">
          {run.n_trading_days}일
        </span>
      </div>
      <div className="mt-0.5 text-[10px] text-muted-foreground/60">
        run_id: {run.run_id.slice(0, 8)}…
      </div>
    </button>
  );
}

export default function AdminBacktestPage() {
  // --- Walk-forward 실행 상태 ---
  const [runPeriodEnd, setRunPeriodEnd] = useState(todayStr());
  const [runNDays, setRunNDays] = useState("60");
  const [runLoading, setRunLoading] = useState(false);
  const [runToast, setRunToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  // --- 실행 목록 ---
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<BacktestRunDetail | null>(null);
  const [selectedRunLoading, setSelectedRunLoading] = useState(false);

  // --- KS 시계열 / LIVE 게이트 (폴링) ---
  const { data: ksTrend } = usePolling<KSTrendPoint[]>(
    "/api/v1/backtest/distribution-check",
    120_000
  );
  const { data: liveGate, mutate: mutateLiveGate } =
    usePolling<LiveGateStatus>("/api/v1/backtest/live-gate-status", 60_000);

  // --- 60일 백필 상태 ---
  const [bfStartDate, setBfStartDate] = useState("");
  const [bfEndDate, setBfEndDate] = useState(todayStr());
  const [bfLoading, setBfLoading] = useState(false);
  const [bfToast, setBfToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  // 목록 로드
  const loadRuns = useCallback(async () => {
    setRunsLoading(true);
    try {
      const data = await getBacktestRuns(10);
      setRuns(data);
    } catch {
      // 무시
    } finally {
      setRunsLoading(false);
    }
  }, []);

  // 상세 로드
  const loadRunDetail = useCallback(async (runId: string) => {
    setSelectedRunId(runId);
    setSelectedRunLoading(true);
    try {
      const detail = await getBacktestRun(runId);
      setSelectedRun(detail);
    } catch {
      setSelectedRun(null);
    } finally {
      setSelectedRunLoading(false);
    }
  }, []);

  // 초기 목록 로드 (한 번만)
  const [initLoaded, setInitLoaded] = useState(false);
  if (!initLoaded) {
    setInitLoaded(true);
    loadRuns();
  }

  // Walk-forward 실행
  const handleRunBacktest = async () => {
    setRunLoading(true);
    setRunToast(null);
    try {
      const result = await runBacktest({
        period_end: runPeriodEnd,
        n_days: runNDays ? parseInt(runNDays, 10) : 60,
      });
      setRunToast({
        type: "success",
        msg: `백테스트 요청 완료 — run_id: ${result.run_id.slice(0, 8)}…`,
      });
      // 목록 새로고침
      await loadRuns();
      void mutateLiveGate();
    } catch (e) {
      setRunToast({
        type: "error",
        msg: e instanceof Error ? e.message : "요청 실패",
      });
    } finally {
      setRunLoading(false);
    }
  };

  // 백필
  const handleBackfill = async () => {
    if (!bfStartDate || !bfEndDate) {
      setBfToast({ type: "error", msg: "시작일 / 종료일을 입력하세요" });
      return;
    }
    setBfLoading(true);
    setBfToast(null);
    try {
      const result = await backfillDaily({
        start_date: bfStartDate,
        end_date: bfEndDate,
      });
      setBfToast({
        type: "success",
        msg: `백필 완료 — status: ${result.status}`,
      });
    } catch (e) {
      setBfToast({
        type: "error",
        msg: e instanceof Error ? e.message : "요청 실패",
      });
    } finally {
      setBfLoading(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* 헤더 */}
      <header className="space-y-1">
        <h1 className="text-lg font-mono font-semibold tracking-wide">
          Admin — Walk-forward 백테스트 (Phase 8.6 Sprint 4)
        </h1>
        <p className="text-xs font-mono text-muted-foreground">
          KS 검정 · Bootstrap CI · LIVE 토글 게이트 · 시뮬-실측 분포 드리프트
          모니터링
        </p>
      </header>

      {/* 1. Walk-forward 실행 */}
      <Card>
        <CardHeader>
          <CardTitle className="font-mono text-sm">
            Walk-forward 실행
          </CardTitle>
          <CardDescription className="font-mono text-[11px]">
            기간 종료일 + 거래일 수 지정 후 백테스트 실행
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-mono text-muted-foreground">
                period_end
              </label>
              <input
                type="date"
                value={runPeriodEnd}
                onChange={(e) => setRunPeriodEnd(e.target.value)}
                className="h-8 rounded border border-border bg-background px-2 font-mono text-[11px] focus:outline-none focus:ring-1 focus:ring-sky-500/60"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-mono text-muted-foreground">
                n_days (거래일)
              </label>
              <input
                type="number"
                value={runNDays}
                min={10}
                max={250}
                onChange={(e) => setRunNDays(e.target.value)}
                className="h-8 w-20 rounded border border-border bg-background px-2 font-mono text-[11px] focus:outline-none focus:ring-1 focus:ring-sky-500/60"
              />
            </div>
            <button
              type="button"
              disabled={runLoading}
              onClick={handleRunBacktest}
              className={cn(
                "h-8 rounded px-4 font-mono text-[11px] transition-colors",
                runLoading
                  ? "bg-muted/40 text-muted-foreground cursor-not-allowed"
                  : "bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 border border-sky-500/40"
              )}
            >
              {runLoading ? "실행 중…" : "▶ 실행"}
            </button>
          </div>
          {runToast && (
            <div
              className={cn(
                "mt-3 rounded px-3 py-2 text-[11px] font-mono",
                runToast.type === "success"
                  ? "bg-emerald-950/30 text-emerald-300 border border-emerald-500/30"
                  : "bg-red-950/30 text-red-300 border border-red-500/30"
              )}
            >
              {runToast.msg}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 2. 최근 실행 결과 */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="font-mono text-sm font-semibold">
            최근 실행 결과
          </h2>
          <button
            type="button"
            onClick={loadRuns}
            className="text-[11px] font-mono text-sky-400 hover:underline focus:outline-none"
          >
            새로고침
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {/* 목록 */}
          <Card>
            <CardContent className="pt-4">
              {runsLoading ? (
                <p className="text-[11px] font-mono text-muted-foreground">
                  로딩 중…
                </p>
              ) : runs.length === 0 ? (
                <p className="text-[11px] font-mono text-muted-foreground">
                  실행 기록 없음
                </p>
              ) : (
                <div className="space-y-1">
                  {runs.map((run) => (
                    <RunRow
                      key={run.run_id}
                      run={run}
                      isSelected={selectedRunId === run.run_id}
                      onClick={() => loadRunDetail(run.run_id)}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 상세 */}
          <div>
            {selectedRunLoading && (
              <Card>
                <CardContent className="pt-4">
                  <p className="text-[11px] font-mono text-muted-foreground">
                    상세 로딩 중…
                  </p>
                </CardContent>
              </Card>
            )}
            {!selectedRunLoading && selectedRun && (
              <BacktestResultTable run={selectedRun} />
            )}
            {!selectedRunLoading && !selectedRun && selectedRunId && (
              <Card>
                <CardContent className="pt-4">
                  <p className="text-[11px] font-mono text-destructive">
                    상세 로드 실패
                  </p>
                </CardContent>
              </Card>
            )}
            {!selectedRunId && (
              <Card className="border-dashed">
                <CardContent className="pt-4">
                  <p className="text-[11px] font-mono text-muted-foreground">
                    왼쪽 목록에서 실행 항목을 클릭하면 tier별 KS 결과가
                    표시됩니다
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </section>

      {/* 3. KS 시계열 + LIVE 게이트 */}
      <div className="grid gap-4 md:grid-cols-2">
        <KsTrendCard points={ksTrend ?? []} />
        {liveGate ? (
          <LiveGateCard status={liveGate} />
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="font-mono text-sm">
                LIVE 토글 게이트
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[11px] font-mono text-muted-foreground">
                로딩 중…
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* 4. 60일 일봉 백필 */}
      <Card className="border-amber-500/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-mono text-sm">
            60일 일봉 백필
            <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-mono text-amber-300">
              admin 전용
            </span>
          </CardTitle>
          <CardDescription className="font-mono text-[11px]">
            일봉 데이터 누락 구간 수동 보충. 운영 주의 — 중복 실행 방지할 것.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-mono text-muted-foreground">
                start_date
              </label>
              <input
                type="date"
                value={bfStartDate}
                onChange={(e) => setBfStartDate(e.target.value)}
                className="h-8 rounded border border-border bg-background px-2 font-mono text-[11px] focus:outline-none focus:ring-1 focus:ring-amber-500/60"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-mono text-muted-foreground">
                end_date
              </label>
              <input
                type="date"
                value={bfEndDate}
                onChange={(e) => setBfEndDate(e.target.value)}
                className="h-8 rounded border border-border bg-background px-2 font-mono text-[11px] focus:outline-none focus:ring-1 focus:ring-amber-500/60"
              />
            </div>
            <button
              type="button"
              disabled={bfLoading}
              onClick={handleBackfill}
              className={cn(
                "h-8 rounded px-4 font-mono text-[11px] transition-colors",
                bfLoading
                  ? "bg-muted/40 text-muted-foreground cursor-not-allowed"
                  : "bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/40"
              )}
            >
              {bfLoading ? "백필 중…" : "백필 실행"}
            </button>
          </div>
          {bfToast && (
            <div
              className={cn(
                "mt-3 rounded px-3 py-2 text-[11px] font-mono",
                bfToast.type === "success"
                  ? "bg-emerald-950/30 text-emerald-300 border border-emerald-500/30"
                  : "bg-red-950/30 text-red-300 border border-red-500/30"
              )}
            >
              {bfToast.msg}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
