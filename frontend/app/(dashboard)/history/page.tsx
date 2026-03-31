"use client";

import { useState } from "react";
import { usePolling } from "@/lib/hooks/use-polling";
import { getPnlColor } from "@/lib/colors";
import { formatKRW, formatRate, formatDateKST, formatTimeHMS } from "@/lib/format";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface TradeHistory {
  id: number;
  stock_code: string;
  strategy_name: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  realized_pnl: number;
  pnl_rate: number;
  holding_duration_sec: number;
  exit_reason: string;
  entry_time: string | null;
  exit_time: string | null;
}

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s}s`;
}

const COLUMNS = [
  "청산시각",
  "종목코드",
  "전략",
  "진입가",
  "청산가",
  "수량",
  "실현손익",
  "수익률",
  "보유시간",
  "청산사유",
];

export default function HistoryPage() {
  const today = formatDateKST();
  const [selectedDate, setSelectedDate] = useState(today);

  const isToday = selectedDate === today;
  const path = `/api/v1/trading/history?target_date=${selectedDate}`;

  const { data: trades, isLoading, error } = usePolling<TradeHistory[]>(
    path,
    isToday ? 5000 : 0
  );

  const totalPnl = trades?.reduce((s, t) => s + t.realized_pnl, 0) ?? 0;
  const avgRate =
    trades && trades.length > 0
      ? trades.reduce((s, t) => s + t.pnl_rate, 0) / trades.length
      : 0;

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">매매 이력</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">
            일자별 체결 내역
          </p>
        </div>
        <input
          type="date"
          value={selectedDate}
          max={today}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="bg-card border border-border/50 rounded-md px-3 py-1.5 text-sm font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-border"
        />
      </div>

      {/* 요약 */}
      {!isLoading && trades && trades.length > 0 && (
        <div className="flex items-center gap-6 rounded-lg border border-border/50 bg-card px-4 py-3">
          <div>
            <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
              총 건수
            </p>
            <p className="text-sm font-mono font-semibold tabular-nums">
              {trades.length}건
            </p>
          </div>
          <div>
            <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
              총 실현손익
            </p>
            <p
              className="text-sm font-mono font-semibold tabular-nums"
              style={{ color: getPnlColor(totalPnl) }}
            >
              {formatKRW(totalPnl)}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
              평균 수익률
            </p>
            <p
              className="text-sm font-mono font-semibold tabular-nums"
              style={{ color: getPnlColor(avgRate) }}
            >
              {formatRate(avgRate)}
            </p>
          </div>
        </div>
      )}

      {error && (
        <p className="text-xs font-mono text-destructive">
          ⚠ 데이터를 불러올 수 없습니다
        </p>
      )}

      {/* 테이블 */}
      <div className="rounded-lg border border-border/50 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/50">
              {COLUMNS.map((h) => (
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
            {isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i} className="border-border/30">
                  {Array.from({ length: COLUMNS.length }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!isLoading && trades?.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={COLUMNS.length}
                  className="text-center py-12 text-xs font-mono text-muted-foreground"
                >
                  해당 날짜의 매매 이력이 없습니다
                </TableCell>
              </TableRow>
            )}

            {trades?.map((trade) => (
              <TableRow
                key={trade.id}
                className="border-border/30 hover:bg-accent/30"
              >
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {formatTimeHMS(trade.exit_time)}
                </TableCell>
                <TableCell>
                  <span className="font-mono font-medium text-sm">
                    {trade.stock_code}
                  </span>
                </TableCell>
                <TableCell>
                  {trade.strategy_name && (
                    <Badge
                      variant="outline"
                      className="text-[10px] font-mono px-1.5 py-0"
                    >
                      {trade.strategy_name}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm text-muted-foreground">
                  {formatKRW(trade.entry_price)}
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm">
                  {formatKRW(trade.exit_price)}
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm">
                  {trade.quantity.toLocaleString()}주
                </TableCell>
                <TableCell
                  className="font-mono tabular-nums text-sm"
                  style={{ color: getPnlColor(trade.realized_pnl) }}
                >
                  {formatKRW(trade.realized_pnl)}
                </TableCell>
                <TableCell
                  className="font-mono tabular-nums text-sm"
                  style={{ color: getPnlColor(trade.pnl_rate) }}
                >
                  {formatRate(trade.pnl_rate)}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {formatDuration(trade.holding_duration_sec)}
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className="text-[10px] font-mono px-1.5 py-0 border-border/50"
                  >
                    {trade.exit_reason}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
