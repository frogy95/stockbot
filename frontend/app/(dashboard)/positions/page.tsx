"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { getPnlColor } from "@/lib/colors";
import { formatKRW, formatRate } from "@/lib/format";
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
import { cn } from "@/lib/utils";

interface Position {
  id: number;
  stock_code: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  unrealized_pnl: number;
  stop_loss: number;
  take_profit: number;
  trailing_activated: boolean;
  entry_time: string | null;
  strategy_name: string | null;
}

function PnlCell({ value, rate }: { value: number; rate: number }) {
  const color = getPnlColor(value);
  return (
    <div>
      <p className="font-mono tabular-nums text-sm" style={{ color }}>
        {formatKRW(value)}
      </p>
      <p className="font-mono tabular-nums text-[11px] text-muted-foreground">
        {formatRate(rate)}
      </p>
    </div>
  );
}

function pnlRate(pos: Position): number {
  if (!pos.avg_price || !pos.quantity) return 0;
  return ((pos.current_price - pos.avg_price) / pos.avg_price) * 100;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function PositionsPage() {
  const { data: positions, isLoading, error } = usePolling<Position[]>(
    "/api/v1/trading/positions"
  );

  const totalUnrealized = positions?.reduce((s, p) => s + p.unrealized_pnl, 0) ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">포지션</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">
            보유 중인 종목
          </p>
        </div>
        {!isLoading && positions && (
          <div className="text-right">
            <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
              미실현 합계
            </p>
            <p
              className="text-base font-mono font-semibold tabular-nums"
              style={{ color: getPnlColor(totalUnrealized) }}
            >
              {formatKRW(totalUnrealized)}
            </p>
          </div>
        )}
      </div>

      {error && (
        <p className="text-xs font-mono text-destructive">⚠ 데이터를 불러올 수 없습니다</p>
      )}

      <div className="rounded-lg border border-border/50 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/50">
              {["종목코드", "수량", "평균가", "현재가", "미실현 손익", "손절/목표", "진입시간", "전략"].map((h) => (
                <TableHead key={h} className="text-[10px] font-mono tracking-widest uppercase text-muted-foreground">
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i} className="border-border/30">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
            {!isLoading && positions?.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12 text-xs font-mono text-muted-foreground">
                  보유 중인 포지션 없음
                </TableCell>
              </TableRow>
            )}
            {positions?.map((pos) => (
              <TableRow key={pos.id} className="border-border/30 hover:bg-accent/30">
                <TableCell>
                  <span className="font-mono font-medium text-sm">{pos.stock_code}</span>
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm">
                  {pos.quantity.toLocaleString()}주
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm text-muted-foreground">
                  {formatKRW(pos.avg_price)}
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm">
                  {formatKRW(pos.current_price)}
                </TableCell>
                <TableCell>
                  <PnlCell value={pos.unrealized_pnl} rate={pnlRate(pos)} />
                </TableCell>
                <TableCell>
                  <div className="space-y-0.5">
                    <p className="font-mono text-[11px] text-loss">
                      손절 {formatKRW(pos.stop_loss)}
                    </p>
                    <p className="font-mono text-[11px] text-profit">
                      목표 {formatKRW(pos.take_profit)}
                    </p>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {formatDateTime(pos.entry_time)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    {pos.strategy_name && (
                      <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0">
                        {pos.strategy_name}
                      </Badge>
                    )}
                    {pos.trailing_activated && (
                      <Badge className="text-[10px] font-mono px-1.5 py-0 bg-amber-500/20 text-amber-400 border-amber-500/30">
                        TR
                      </Badge>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
