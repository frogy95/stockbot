"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatKRW } from "@/lib/format";
import { apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";

interface SignalInfo {
  stock_code: string;
  signal_type: string;
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  strategy_name: string;
}

interface ApprovalCardProps {
  token: string;
  signal: SignalInfo;
  quantity: number;
  expires_in_sec: number;
  onAction: () => void;
}

export function ApprovalCard({
  token,
  signal,
  quantity,
  expires_in_sec,
  onAction,
}: ApprovalCardProps) {
  const [remaining, setRemaining] = useState(expires_in_sec);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (remaining <= 0) return;
    timerRef.current = setInterval(() => {
      setRemaining((prev) => Math.max(prev - 1, 0));
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 카운트다운 0 도달 시 타이머 정지
  useEffect(() => {
    if (remaining === 0 && timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [remaining]);

  const handleAction = useCallback(
    async (action: "approve" | "reject") => {
      setLoading(true);
      try {
        await apiPost(`/api/v1/trading/signals/${token}/${action}`, {});
        onAction();
      } catch {
        // 오류 시 loading 해제 후 사용자가 재시도 가능
      } finally {
        setLoading(false);
      }
    },
    [token, onAction]
  );

  const progressPct = expires_in_sec > 0 ? (remaining / expires_in_sec) * 100 : 0;
  const isExpired = remaining <= 0;
  const isLow = remaining <= 10;
  const isBuy = signal.signal_type === "BUY";

  return (
    <Card className="relative overflow-hidden border-border/50 bg-card">
      {/* 만료 오버레이 */}
      {isExpired && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 rounded-lg">
          <span className="font-mono text-sm font-semibold text-muted-foreground">
            시간 초과
          </span>
        </div>
      )}

      {/* 카운트다운 프로그레스 바 */}
      <div className="h-1 w-full bg-border/40">
        <div
          className={cn(
            "h-full transition-all duration-1000 ease-linear",
            isLow ? "bg-red-500" : "bg-emerald-500"
          )}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      <CardHeader className="px-4 pt-3 pb-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono font-semibold text-sm">
              {signal.stock_code}
            </span>
            <Badge
              className={cn(
                "text-[10px] font-mono px-1.5 py-0",
                isBuy
                  ? "bg-red-500/20 text-red-400 border-red-500/30"
                  : "bg-blue-500/20 text-blue-400 border-blue-500/30"
              )}
              variant="outline"
            >
              {signal.signal_type}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "font-mono text-xs tabular-nums",
                isLow ? "text-red-400" : "text-muted-foreground"
              )}
            >
              {remaining}초
            </span>
          </div>
        </div>
        <p className="text-[10px] font-mono text-muted-foreground mt-0.5">
          {signal.strategy_name}
        </p>
      </CardHeader>

      <CardContent className="px-4 pt-3 pb-4 space-y-3">
        {/* 신뢰도 */}
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-muted-foreground">신뢰도</span>
          <span className="tabular-nums font-semibold">
            {(signal.confidence * 100).toFixed(1)}%
          </span>
        </div>

        {/* 가격 정보 */}
        <div className="grid grid-cols-3 gap-2 rounded-md bg-muted/30 px-3 py-2">
          <div className="text-center">
            <p className="text-[10px] font-mono text-muted-foreground mb-0.5">진입가</p>
            <p className="font-mono text-xs tabular-nums">{formatKRW(signal.entry_price)}</p>
          </div>
          <div className="text-center">
            <p className="text-[10px] font-mono text-muted-foreground mb-0.5">손절가</p>
            <p className="font-mono text-xs tabular-nums text-blue-400">
              {formatKRW(signal.stop_loss)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-[10px] font-mono text-muted-foreground mb-0.5">목표가</p>
            <p className="font-mono text-xs tabular-nums text-red-400">
              {formatKRW(signal.take_profit)}
            </p>
          </div>
        </div>

        {/* 수량 */}
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-muted-foreground">수량</span>
          <span className="tabular-nums">{quantity.toLocaleString()}주</span>
        </div>

        {/* 버튼 */}
        <div className="flex gap-2 pt-1">
          <Button
            className="flex-1 h-8 text-xs font-mono bg-red-600 hover:bg-red-700 text-white"
            disabled={loading || isExpired}
            onClick={() => handleAction("approve")}
          >
            {loading ? "처리 중…" : "승인"}
          </Button>
          <Button
            variant="outline"
            className="flex-1 h-8 text-xs font-mono border-border/50"
            disabled={loading || isExpired}
            onClick={() => handleAction("reject")}
          >
            거절
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
