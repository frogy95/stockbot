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
