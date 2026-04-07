"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiFetch } from "@/lib/api";

interface ModeSwitchProps {
  currentEnv: string; // "paper" | "live"
  onSuccess: () => void;
}

type DialogStep = "closed" | "step1" | "step2";

export function ModeSwitch({ currentEnv, onSuccess }: ModeSwitchProps) {
  const [step, setStep] = useState<DialogStep>("closed");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const targetEnv = currentEnv === "paper" ? "live" : "paper";
  const confirmMessage =
    currentEnv === "paper"
      ? "모의(PAPER) → 실전(LIVE)으로 전환하시겠습니까?"
      : "실전(LIVE) → 모의(PAPER)로 전환하시겠습니까?";

  function handleOpen() {
    setStep("step1");
    setError(null);
    setPassword("");
  }

  function handleClose() {
    setStep("closed");
    setError(null);
    setPassword("");
  }

  function handleStep1Confirm() {
    setError(null);
    setStep("step2");
  }

  async function handleStep2Confirm() {
    setIsLoading(true);
    setError(null);

    try {
      const resp = await apiFetch("/api/v1/settings/mode", {
        method: "PUT",
        body: JSON.stringify({ target_env: targetEnv, password }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        if (resp.status === 423) {
          setError("장중(09:00~15:30)에는 모드를 전환할 수 없습니다");
        } else if (resp.status === 409) {
          setError("활성 포지션이 있어 전환할 수 없습니다");
        } else if (resp.status === 403) {
          setError("비밀번호가 올바르지 않습니다");
        } else {
          setError((data as { detail?: string }).detail ?? "모드 전환에 실패했습니다");
        }
        return;
      }

      handleClose();
      onSuccess();
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
          현재 모드
        </span>
        {currentEnv === "live" ? (
          <Badge className="font-mono text-xs bg-red-600 hover:bg-red-600 text-white border-red-600">
            LIVE
          </Badge>
        ) : (
          <Badge className="font-mono text-xs bg-green-700 hover:bg-green-700 text-white border-green-700">
            PAPER
          </Badge>
        )}
      </div>

      <Button variant="outline" size="sm" className="font-mono text-xs" onClick={handleOpen}>
        모드 전환
      </Button>

      {/* Step 1: 전환 확인 */}
      <Dialog open={step === "step1"} onOpenChange={(open) => { if (!open) handleClose(); }}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>거래 모드 전환</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{confirmMessage}</p>
          {error && (
            <div className="text-xs text-destructive font-mono bg-destructive/10 rounded px-3 py-2">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={handleClose}>
              취소
            </Button>
            <Button size="sm" onClick={handleStep1Confirm}>
              확인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Step 2: 비밀번호 입력 */}
      <Dialog open={step === "step2"} onOpenChange={(open) => { if (!open) handleClose(); }}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>비밀번호 확인</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground font-mono">
              비밀번호를 입력하세요
            </p>
            <Input
              type="password"
              placeholder="비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isLoading) handleStep2Confirm();
              }}
              className="font-mono text-sm"
              autoFocus
            />
          </div>
          {error && (
            <div className="text-xs text-destructive font-mono bg-destructive/10 rounded px-3 py-2">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={handleClose} disabled={isLoading}>
              취소
            </Button>
            <Button
              size="sm"
              onClick={handleStep2Confirm}
              disabled={isLoading || !password}
            >
              {isLoading ? "처리 중..." : "최종 확인"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TradingModeSwitch: 매매 모드 전환 (manual / semi-auto / auto)
// ─────────────────────────────────────────────────────────────────────────────

type TradingMode = "manual" | "semi-auto" | "auto";
type TradingDialogStep = "closed" | "warn" | "password";

const TRADING_MODE_LABELS: Record<TradingMode, string> = {
  manual: "수동",
  "semi-auto": "반자동",
  auto: "자동",
};

interface TradingModeSwitchProps {
  currentMode: string;
  onSuccess: () => void;
}

export function TradingModeSwitch({ currentMode, onSuccess }: TradingModeSwitchProps) {
  const [pendingMode, setPendingMode] = useState<TradingMode | null>(null);
  const [step, setStep] = useState<TradingDialogStep>("closed");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function handleSelectChange(value: string) {
    if (value === currentMode) return;
    const target = value as TradingMode;
    setPendingMode(target);
    setError(null);
    setPassword("");
    // 자동 모드로 전환 시에는 경고 → 비밀번호 2단계
    setStep(target === "auto" ? "warn" : "password");
  }

  function handleClose() {
    setStep("closed");
    setPendingMode(null);
    setError(null);
    setPassword("");
  }

  function handleWarnConfirm() {
    setError(null);
    setStep("password");
  }

  async function handlePasswordConfirm() {
    if (!pendingMode) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const resp = await apiFetch("/api/v1/settings/trading-mode", {
        method: "PUT",
        body: JSON.stringify({ target_mode: pendingMode, password }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        if (resp.status === 423) {
          setError("장중(09:00~15:30)에는 모드를 전환할 수 없습니다");
        } else if (resp.status === 409) {
          setError("활성 포지션이 있어 자동 모드로 전환할 수 없습니다");
        } else if (resp.status === 403) {
          setError("비밀번호가 올바르지 않습니다");
        } else {
          setError((data as { detail?: string }).detail ?? "모드 전환에 실패했습니다");
        }
        return;
      }

      handleClose();
      onSuccess();
    } finally {
      setIsSubmitting(false);
    }
  }

  const modeLabel = (m: string) =>
    TRADING_MODE_LABELS[m as TradingMode] ?? m;

  return (
    <div className="flex items-center gap-4">
      <Select value={currentMode} onValueChange={handleSelectChange}>
        <SelectTrigger className="font-mono text-xs w-36 h-8">
          <SelectValue placeholder="모드 선택" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="manual" className="font-mono text-xs">
            수동 (Manual)
          </SelectItem>
          <SelectItem value="semi-auto" className="font-mono text-xs">
            반자동 (Semi-Auto)
          </SelectItem>
          <SelectItem value="auto" className="font-mono text-xs">
            자동 (Auto)
          </SelectItem>
        </SelectContent>
      </Select>

      {/* Step 1 (auto 전환 시): 경고 메시지 */}
      <Dialog open={step === "warn"} onOpenChange={(open) => { if (!open) handleClose(); }}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>자동 모드 전환 경고</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>
              자동 모드에서는 신호 발생 시 즉시 주문됩니다.
            </p>
            <p>
              적응형/기본 후보는 반자동으로 처리됩니다.
            </p>
          </div>
          {error && (
            <div className="text-xs text-destructive font-mono bg-destructive/10 rounded px-3 py-2">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={handleClose}>
              취소
            </Button>
            <Button variant="destructive" size="sm" onClick={handleWarnConfirm}>
              계속
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 비밀번호 확인 Dialog (모든 모드 전환 공통) */}
      <Dialog open={step === "password"} onOpenChange={(open) => { if (!open) handleClose(); }}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>
              매매 모드 전환 — {pendingMode ? modeLabel(pendingMode) : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground font-mono">
              비밀번호를 입력하세요
            </p>
            <Input
              type="password"
              placeholder="비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isSubmitting) handlePasswordConfirm();
              }}
              className="font-mono text-sm"
              autoFocus
            />
          </div>
          {error && (
            <div className="text-xs text-destructive font-mono bg-destructive/10 rounded px-3 py-2">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={handleClose} disabled={isSubmitting}>
              취소
            </Button>
            <Button
              size="sm"
              onClick={handlePasswordConfirm}
              disabled={isSubmitting || !password}
            >
              {isSubmitting ? "처리 중..." : "확인"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
