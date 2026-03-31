"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    const ok = await login(password);
    if (ok) {
      router.push("/");
      return;
    }
    setError("비밀번호가 올바르지 않거나 잠금 상태입니다");
    setPassword("");
    setIsLoading(false);
  }

  return (
    <div className="border border-border/60 bg-card/80 backdrop-blur-sm rounded-lg p-8 shadow-2xl">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-[10px] font-mono text-muted-foreground tracking-[0.2em] uppercase">
            System Access
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">StockBot</h1>
        <p className="text-sm text-muted-foreground mt-1 font-mono">
          한국 주식/ETF 자동 매매 시스템
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-mono text-muted-foreground tracking-widest uppercase">
            Password
          </label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoFocus
            className="font-mono bg-background/60 border-border/60 focus:border-red-500/60 focus:ring-red-500/20 h-10"
          />
        </div>

        {error && (
          <p className="text-xs font-mono text-red-400 border border-red-500/20 bg-red-500/5 rounded px-3 py-2">
            ⚠ {error}
          </p>
        )}

        <Button
          type="submit"
          disabled={isLoading || !password}
          className="w-full h-10 font-mono text-sm tracking-wider bg-zinc-100 text-zinc-900 hover:bg-zinc-200 disabled:opacity-40"
        >
          {isLoading ? "인증 중..." : "접속"}
        </Button>
      </form>

      <div className="mt-6 pt-4 border-t border-border/40">
        <p className="text-[10px] font-mono text-muted-foreground/50 text-center tracking-wider">
          STOCKBOT v0.4 · AUTHORIZED ACCESS ONLY
        </p>
      </div>
    </div>
  );
}
