"use client";

import { useState } from "react";
import { usePolling } from "@/lib/hooks/use-polling";
import { formatKRW } from "@/lib/format";
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

interface Order {
  id: number;
  signal_id: number | null;
  stock_code: string;
  order_type: "buy" | "sell";
  order_no: string | null;
  quantity: number;
  price: number;
  order_division: string;
  status: "pending" | "submitted" | "filled" | "cancelled" | "failed";
  submitted_at: string | null;
  filled_at: string | null;
}

const STATUS_TABS = [
  { key: null, label: "전체" },
  { key: "pending", label: "대기" },
  { key: "submitted", label: "제출" },
  { key: "filled", label: "체결" },
  { key: "cancelled", label: "취소" },
  { key: "failed", label: "실패" },
] as const;

const STATUS_STYLES: Record<Order["status"], string> = {
  pending:   "bg-zinc-700/40 text-zinc-300 border-zinc-600/40",
  submitted: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  filled:    "bg-green-500/15 text-green-400 border-green-500/30",
  cancelled: "bg-zinc-700/30 text-zinc-500 border-zinc-600/30",
  failed:    "bg-red-500/15 text-red-400 border-red-500/30",
};

const STATUS_LABELS: Record<Order["status"], string> = {
  pending: "대기", submitted: "제출", filled: "체결", cancelled: "취소", failed: "실패",
};

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export default function OrdersPage() {
  const [activeStatus, setActiveStatus] = useState<Order["status"] | null>(null);
  const url = activeStatus
    ? `/api/v1/trading/orders?status=${activeStatus}`
    : "/api/v1/trading/orders";

  const { data: orders, isLoading, error } = usePolling<Order[]>(url);

  const counts = orders
    ? Object.fromEntries(
        STATUS_TABS.slice(1).map(({ key }) => [
          key,
          orders.filter((o) => o.status === key).length,
        ])
      )
    : {};

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">주문 현황</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">오늘의 주문 내역</p>
      </div>

      {/* 상태 필터 탭 */}
      <div className="flex gap-1 border-b border-border/40 pb-0">
        {STATUS_TABS.map(({ key, label }) => (
          <button
            key={String(key)}
            onClick={() => setActiveStatus(key as Order["status"] | null)}
            className={cn(
              "px-3 py-2 text-xs font-mono rounded-t transition-colors",
              "hover:text-foreground",
              activeStatus === key
                ? "text-foreground border-b-2 border-primary -mb-px"
                : "text-muted-foreground"
            )}
          >
            {label}
            {key && orders && counts[key] != null && (
              <span className="ml-1.5 text-[10px] text-muted-foreground">
                {counts[key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-xs font-mono text-destructive">⚠ 데이터를 불러올 수 없습니다</p>
      )}

      <div className="rounded-lg border border-border/50 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/50">
              {["종목코드", "구분", "수량", "가격", "주문번호", "상태", "제출", "체결"].map((h) => (
                <TableHead key={h} className="text-[10px] font-mono tracking-widest uppercase text-muted-foreground">
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i} className="border-border/30">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <TableCell key={j}><Skeleton className="h-4 w-14" /></TableCell>
                  ))}
                </TableRow>
              ))}
            {!isLoading && orders?.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12 text-xs font-mono text-muted-foreground">
                  주문 내역 없음
                </TableCell>
              </TableRow>
            )}
            {orders?.map((order) => (
              <TableRow key={order.id} className="border-border/30 hover:bg-accent/30">
                <TableCell className="font-mono font-medium text-sm">{order.stock_code}</TableCell>
                <TableCell>
                  <Badge
                    className={cn(
                      "text-[10px] font-mono px-1.5 py-0 border",
                      order.order_type === "buy"
                        ? "bg-red-500/15 text-red-400 border-red-500/30"
                        : "bg-blue-500/15 text-blue-400 border-blue-500/30"
                    )}
                  >
                    {order.order_type === "buy" ? "매수" : "매도"}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm">{order.quantity.toLocaleString()}주</TableCell>
                <TableCell className="font-mono tabular-nums text-sm">{formatKRW(order.price)}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{order.order_no ?? "—"}</TableCell>
                <TableCell>
                  <Badge className={cn("text-[10px] font-mono px-1.5 py-0 border", STATUS_STYLES[order.status])}>
                    {STATUS_LABELS[order.status]}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{formatTime(order.submitted_at)}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{formatTime(order.filled_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
