"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";
import { getPnlColor } from "@/lib/colors";
import { formatKRW, formatRate, formatDateKST } from "@/lib/format";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface TradeHistory {
  id: number;
  stock_code: string;
  realized_pnl: number;
  pnl_rate: number;
  trade_date: string;
}

interface DailyStats {
  date: string;
  trade_count: number;
  total_pnl: number;
  avg_pnl_rate: number;
  max_profit: number;
  max_loss: number;
}

const COLS = ["날짜", "거래건수", "총 실현손익", "평균수익률", "최대수익", "최대손실"];

function getDatesInRange(start: string, end: string): string[] {
  const dates: string[] = [];
  const cur = new Date(start);
  const endDate = new Date(end);
  while (cur <= endDate) {
    dates.push(formatDateKST(new Date(cur)));
    cur.setDate(cur.getDate() + 1);
  }
  return dates;
}

function aggregateDay(date: string, trades: TradeHistory[]): DailyStats {
  const total_pnl = trades.reduce((s, t) => s + t.realized_pnl, 0);
  const avg_pnl_rate =
    trades.length > 0
      ? trades.reduce((s, t) => s + t.pnl_rate, 0) / trades.length
      : 0;
  const max_profit = trades.reduce(
    (max, t) => (t.realized_pnl > max ? t.realized_pnl : max),
    0
  );
  const max_loss = trades.reduce(
    (min, t) => (t.realized_pnl < min ? t.realized_pnl : min),
    0
  );
  return {
    date,
    trade_count: trades.length,
    total_pnl,
    avg_pnl_rate,
    max_profit,
    max_loss,
  };
}

export default function AnalyticsPage() {
  const today = formatDateKST();
  const thirtyDaysAgo = formatDateKST(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000));

  const [startDate, setStartDate] = useState(thirtyDaysAgo);
  const [endDate, setEndDate] = useState(today);
  const [dailyStats, setDailyStats] = useState<DailyStats[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const dates = getDatesInRange(startDate, endDate);
      const settled = await Promise.allSettled(
        dates.map((date) =>
          apiGet<TradeHistory[]>(`/api/v1/trading/history?target_date=${date}`).then(
            (trades) => (trades.length > 0 ? aggregateDay(date, trades) : null)
          )
        )
      );
      const results = settled
        .filter(
          (r): r is PromiseFulfilledResult<DailyStats> =>
            r.status === "fulfilled" && r.value !== null
        )
        .map((r) => r.value)
        .sort((a, b) => b.date.localeCompare(a.date));
      setDailyStats(results);
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalTradeCount = dailyStats.reduce((s, d) => s + d.trade_count, 0);
  const cumulativePnl = dailyStats.reduce((s, d) => s + d.total_pnl, 0);
  const avgPnlRate =
    dailyStats.length > 0
      ? dailyStats.reduce((s, d) => s + d.avg_pnl_rate, 0) / dailyStats.length
      : 0;

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">분석</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">
            일별 실현 손익 내역
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="font-mono text-xs"
          onClick={loadData}
          disabled={loading}
        >
          새로고침
        </Button>
      </div>

      {/* 날짜 범위 선택 */}
      <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-card p-3">
        <span className="text-xs font-mono text-muted-foreground">기간</span>
        <input
          type="date"
          value={startDate}
          max={endDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="bg-transparent border border-border/50 rounded px-2 py-1 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-border"
        />
        <span className="text-xs font-mono text-muted-foreground">~</span>
        <input
          type="date"
          value={endDate}
          min={startDate}
          max={today}
          onChange={(e) => setEndDate(e.target.value)}
          className="bg-transparent border border-border/50 rounded px-2 py-1 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-border"
        />
      </div>

      {/* 테이블 */}
      <div className="rounded-lg border border-border/50 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/50">
              {COLS.map((h) => (
                <TableHead
                  key={h}
                  className="text-[10px] font-mono tracking-widest uppercase text-muted-foreground"
                >
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i} className="border-border/30">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}

            {!loading && dailyStats.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center py-12 text-xs font-mono text-muted-foreground"
                >
                  해당 기간의 매매 데이터가 없습니다
                </TableCell>
              </TableRow>
            )}

            {!loading &&
              dailyStats.map((row) => (
                <TableRow
                  key={row.date}
                  className="border-border/30 hover:bg-accent/30"
                >
                  <TableCell className="font-mono text-sm">
                    {row.date}
                  </TableCell>
                  <TableCell className="font-mono tabular-nums text-sm text-muted-foreground">
                    {row.trade_count}건
                  </TableCell>
                  <TableCell
                    className="font-mono tabular-nums text-sm"
                    style={{ color: getPnlColor(row.total_pnl) }}
                  >
                    {formatKRW(row.total_pnl)}
                  </TableCell>
                  <TableCell
                    className="font-mono tabular-nums text-sm"
                    style={{ color: getPnlColor(row.avg_pnl_rate) }}
                  >
                    {formatRate(row.avg_pnl_rate)}
                  </TableCell>
                  <TableCell
                    className="font-mono tabular-nums text-sm"
                    style={{ color: getPnlColor(row.max_profit) }}
                  >
                    {formatKRW(row.max_profit)}
                  </TableCell>
                  <TableCell
                    className="font-mono tabular-nums text-sm"
                    style={{ color: getPnlColor(row.max_loss) }}
                  >
                    {formatKRW(row.max_loss)}
                  </TableCell>
                </TableRow>
              ))}

            {/* 합계 행 */}
            {!loading && dailyStats.length > 0 && (
              <TableRow className="border-t border-border/50 bg-muted/20 hover:bg-muted/30">
                <TableCell className="font-mono text-xs text-muted-foreground uppercase tracking-widest">
                  합계
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm font-semibold">
                  {totalTradeCount}건
                </TableCell>
                <TableCell
                  className="font-mono tabular-nums text-sm font-semibold"
                  style={{ color: getPnlColor(cumulativePnl) }}
                >
                  {formatKRW(cumulativePnl)}
                </TableCell>
                <TableCell
                  className="font-mono tabular-nums text-sm font-semibold"
                  style={{ color: getPnlColor(avgPnlRate) }}
                >
                  {formatRate(avgPnlRate)}
                </TableCell>
                <TableCell />
                <TableCell />
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
