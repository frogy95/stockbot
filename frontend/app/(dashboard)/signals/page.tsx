"use client";

import { useEffect } from "react";
import { usePolling } from "@/lib/hooks/use-polling";
import { ApprovalCard } from "@/components/signals/approval-card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatKRW, formatDateKST, formatTimeHMS } from "@/lib/format";
import { cn } from "@/lib/utils";

// ─── 타입 선언 ──────────────────────────────────────────────────────────────

interface PendingSignal {
  token: string;
  signal: {
    stock_code: string;
    signal_type: string;
    confidence: number;
    entry_price: number;
    stop_loss: number;
    take_profit: number;
    strategy_name: string;
  };
  quantity: number;
  expires_in_sec: number;
}

interface PendingResponse {
  pending: PendingSignal[];
  count: number;
}

interface HistorySignal {
  id: number;
  stock_code: string;
  signal_type: string;
  confidence: number | null;
  entry_price: number;
  status: string;
  created_at: string | null;
}

const STATUS_LABEL: Record<string, string> = {
  approved: "승인",
  rejected: "거절",
  expired: "만료",
  pending: "대기",
};

function StatusBadge({ status }: { status: string }) {
  const label = STATUS_LABEL[status] ?? status;
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-[10px] font-mono px-1.5 py-0",
        status === "approved" && "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
        status === "rejected" && "bg-blue-500/20 text-blue-400 border-blue-500/30",
        status === "expired"  && "bg-muted/50 text-muted-foreground border-border/40",
        status === "pending"  && "bg-amber-500/20 text-amber-400 border-amber-500/30"
      )}
    >
      {label}
    </Badge>
  );
}

// ─── 페이지 컴포넌트 ─────────────────────────────────────────────────────────

export default function SignalsPage() {
  const {
    data: pendingData,
    isLoading: pendingLoading,
    mutate: refreshPending,
  } = usePolling<PendingResponse>(
    "/api/v1/trading/signals/pending",
    (data) => (data && data.count > 0 ? 3000 : 5000)
  );

  const { data: history, isLoading: historyLoading } = usePolling<HistorySignal[]>(
    `/api/v1/trading/signals?target_date=${formatDateKST()}`,
    5000
  );

  const pendingCount = pendingData?.count ?? 0;

  // 동적 document.title
  useEffect(() => {
    document.title = pendingCount > 0 ? `(${pendingCount}) StockBot` : "StockBot";
    return () => {
      document.title = "StockBot";
    };
  }, [pendingCount]);

  return (
    <div className="space-y-6">
      {/* ── 헤더 ── */}
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight">매매 신호</h1>
        {pendingCount > 0 && (
          <Badge className="font-mono text-xs bg-amber-500/20 text-amber-400 border-amber-500/30">
            {pendingCount}
          </Badge>
        )}
      </div>

      {/* ── 대기 중인 신호 섹션 ── */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-widest font-mono">
            승인 대기
          </h2>
          {pendingCount > 0 && (
            <Badge
              variant="outline"
              className="text-[10px] font-mono px-1.5 py-0 bg-amber-500/20 text-amber-400 border-amber-500/30"
            >
              {pendingCount}
            </Badge>
          )}
        </div>

        {pendingLoading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-52 rounded-lg" />
            ))}
          </div>
        )}

        {!pendingLoading && pendingCount === 0 && (
          <p className="text-xs font-mono text-muted-foreground py-6 text-center border border-border/30 rounded-lg">
            대기 중인 신호가 없습니다
          </p>
        )}

        {!pendingLoading && pendingData && pendingData.pending.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {pendingData.pending.map((item) => (
              <ApprovalCard
                key={item.token}
                token={item.token}
                signal={item.signal}
                quantity={item.quantity}
                expires_in_sec={item.expires_in_sec}
                onAction={refreshPending}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── 히스토리 섹션 ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-widest font-mono">
          오늘 신호 이력
        </h2>

        <div className="rounded-lg border border-border/50 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border/50">
                {["시각", "종목코드", "방향", "신뢰도", "진입가", "상태"].map((h) => (
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
              {historyLoading &&
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i} className="border-border/30">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 w-16" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}

              {!historyLoading && (!history || history.length === 0) && (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center py-10 text-xs font-mono text-muted-foreground"
                  >
                    오늘 발생한 신호가 없습니다
                  </TableCell>
                </TableRow>
              )}

              {history?.map((sig) => {
                const isBuy = sig.signal_type === "BUY";
                return (
                  <TableRow key={sig.id} className="border-border/30 hover:bg-accent/30">
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {formatTimeHMS(sig.created_at)}
                    </TableCell>
                    <TableCell>
                      <span className="font-mono font-medium text-sm">
                        {sig.stock_code}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] font-mono px-1.5 py-0",
                          isBuy
                            ? "bg-red-500/20 text-red-400 border-red-500/30"
                            : "bg-blue-500/20 text-blue-400 border-blue-500/30"
                        )}
                      >
                        {sig.signal_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono tabular-nums text-xs">
                      {sig.confidence != null
                        ? `${(sig.confidence * 100).toFixed(1)}%`
                        : "—"}
                    </TableCell>
                    <TableCell className="font-mono tabular-nums text-xs">
                      {formatKRW(sig.entry_price)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={sig.status} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}
