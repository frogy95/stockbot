"use client";

import { useState } from "react";

import { resetRiskCounters } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface ResetButtonProps {
  /** 현재 거래 환경 (live | paper) */
  tradingEnv?: string;
  /** 성공 시 상위 컴포넌트 재조회 트리거 */
  onResetSuccess?: () => void;
}

/**
 * 일일 리스크 카운터 리셋 버튼 — 2단계 확인 다이얼로그 + LIVE 경고 배지.
 * Phase 8 Sprint 2 Task 7: Hotfix #153 `POST /api/v1/trading/risk/reset` 엔드포인트 소비.
 */
export function ResetRiskButton({ tradingEnv, onResetSuccess }: ResetButtonProps) {
  const [open, setOpen] = useState(false);
  const [ack, setAck] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const isLive = (tradingEnv ?? "").toLowerCase() === "live";

  const onClose = () => {
    setOpen(false);
    // 닫힘 애니메이션 후 상태 초기화
    setTimeout(() => {
      setAck(false);
      setError(null);
      setDone(false);
    }, 200);
  };

  const handleReset = async () => {
    setLoading(true);
    setError(null);
    try {
      await resetRiskCounters();
      setDone(true);
      onResetSuccess?.();
      setTimeout(onClose, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "리셋 요청 중 오류 발생");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm" className="font-mono text-xs">
          일일 리스크 카운터 리셋
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            리스크 카운터 리셋
            {isLive ? (
              <Badge variant="destructive">⚠️ LIVE 실전</Badge>
            ) : (
              <Badge variant="secondary">PAPER 모의</Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            연속 손절 / 비상 정지 / 일일 거래 카운터가 모두 0으로 초기화됩니다.
            {isLive
              ? " 실전 환경에서는 이 작업이 즉시 매매 재개를 허용하므로 신중히 사용하세요."
              : " 모의 환경에서 안전하게 초기화합니다."}
          </DialogDescription>
        </DialogHeader>

        {done ? (
          <p className="text-sm text-[color:var(--color-chart-2,#22c55e)]">
            ✅ 리셋 완료 — 카운터가 초기화되었습니다.
          </p>
        ) : (
          <>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={ack}
                onChange={(e) => setAck(e.target.checked)}
                className="h-4 w-4"
              />
              <span>위험을 이해했으며 리셋을 실행합니다.</span>
            </label>
            {error && (
              <p className="text-sm text-destructive font-mono">⚠ {error}</p>
            )}
          </>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
            취소
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleReset}
            disabled={!ack || loading || done}
          >
            {loading ? "리셋 중..." : "리셋 실행"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
