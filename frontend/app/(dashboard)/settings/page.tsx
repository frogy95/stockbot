"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiGet, apiPut } from "@/lib/api";
import { ModeSwitch, TradingModeSwitch } from "@/components/settings/mode-switch";
import { ModeIndicator } from "@/components/mode-indicator";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface SystemSetting {
  key: string;
  value: string;
  value_type: string;
  category: string;
  description?: string;
}

interface AuditLog {
  id: number;
  action: string;
  target_key: string;
  old_value: string | null;
  new_value: string | null;
  actor: string;
  ip_address: string | null;
  created_at: string | null;
}

function isMarketHours(): boolean {
  const now = new Date();
  const kst = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }));
  const h = kst.getHours();
  const m = kst.getMinutes();
  const weekday = kst.getDay(); // 0=Sun, 6=Sat
  if (weekday === 0 || weekday === 6) return false;
  return (h > 9 || (h === 9 && m >= 0)) && (h < 15 || (h === 15 && m <= 30));
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

// 인라인 편집 가능한 설정 테이블 행
function SettingRow({
  setting,
  disabled,
  onSaved,
}: {
  setting: SystemSetting;
  disabled: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [inputValue, setInputValue] = useState(setting.value);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);
    try {
      await apiPut(`/api/v1/settings/${setting.key}`, { value: inputValue });
      setEditing(false);
      onSaved();
    } catch {
      setSaveError("저장에 실패했습니다");
    } finally {
      setIsSaving(false);
    }
  }

  function handleCancel() {
    setInputValue(setting.value);
    setSaveError(null);
    setEditing(false);
  }

  return (
    <TableRow className="border-border/30 hover:bg-accent/30">
      <TableCell className="font-mono text-xs">{setting.key}</TableCell>
      <TableCell>
        {editing ? (
          <div className="flex items-center gap-2">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="font-mono text-xs h-7 w-40"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave();
                if (e.key === "Escape") handleCancel();
              }}
              autoFocus
            />
            {saveError && (
              <span className="text-xs text-destructive font-mono">{saveError}</span>
            )}
          </div>
        ) : (
          <span className="font-mono tabular-nums text-sm">{setting.value}</span>
        )}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {setting.description ?? "—"}
      </TableCell>
      <TableCell>
        {editing ? (
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="default"
              className="h-6 text-xs px-2 font-mono"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? "저장 중..." : "저장"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-6 text-xs px-2 font-mono"
              onClick={handleCancel}
              disabled={isSaving}
            >
              취소
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            variant="outline"
            className="h-6 text-xs px-2 font-mono"
            onClick={() => { setInputValue(setting.value); setEditing(true); }}
            disabled={disabled}
          >
            편집
          </Button>
        )}
      </TableCell>
    </TableRow>
  );
}

// 설정 섹션 테이블
function SettingsTable({
  title,
  settings,
  isLoading,
  error,
  marketLocked,
  onRefresh,
}: {
  title: string;
  settings: SystemSetting[] | null;
  isLoading: boolean;
  error: boolean;
  marketLocked: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        {marketLocked && (
          <Badge className="text-[10px] font-mono px-1.5 py-0 bg-amber-500/20 text-amber-400 border-amber-500/30">
            장중 잠금
          </Badge>
        )}
      </div>
      {error && (
        <p className="text-xs font-mono text-destructive">⚠ 데이터를 불러올 수 없습니다</p>
      )}
      <div className="rounded-lg border border-border/50 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/50">
              {["설정키", "현재값", "설명", ""].map((h, i) => (
                <TableHead
                  key={i}
                  className="text-[10px] font-mono tracking-widest uppercase text-muted-foreground"
                >
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i} className="border-border/30">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            {!isLoading && settings?.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center py-8 text-xs font-mono text-muted-foreground"
                >
                  설정 항목 없음
                </TableCell>
              </TableRow>
            )}
            {settings?.map((s) => (
              <SettingRow
                key={s.key}
                setting={s}
                disabled={marketLocked}
                onSaved={onRefresh}
              />
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

interface TradingModeSetting {
  trading_mode: string;
}

export default function SettingsPage() {
  const { user } = useAuth();

  const [riskSettings, setRiskSettings] = useState<SystemSetting[] | null>(null);
  const [riskLoading, setRiskLoading] = useState(true);
  const [riskError, setRiskError] = useState(false);

  const [tradingSettings, setTradingSettings] = useState<SystemSetting[] | null>(null);
  const [tradingLoading, setTradingLoading] = useState(true);
  const [tradingError, setTradingError] = useState(false);

  const [auditLogs, setAuditLogs] = useState<AuditLog[] | null>(null);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditError, setAuditError] = useState(false);

  const [tradingMode, setTradingMode] = useState<string | null>(null);
  const [tradingModeLoading, setTradingModeLoading] = useState(true);

  const marketHours = isMarketHours();

  const fetchRisk = useCallback(async () => {
    setRiskLoading(true);
    setRiskError(false);
    try {
      const data = await apiGet<SystemSetting[]>("/api/v1/settings?category=risk");
      setRiskSettings(data);
    } catch {
      setRiskError(true);
    } finally {
      setRiskLoading(false);
    }
  }, []);

  const fetchTrading = useCallback(async () => {
    setTradingLoading(true);
    setTradingError(false);
    try {
      const data = await apiGet<SystemSetting[]>("/api/v1/settings?category=trading");
      setTradingSettings(data);
    } catch {
      setTradingError(true);
    } finally {
      setTradingLoading(false);
    }
  }, []);

  const fetchAuditLogs = useCallback(async () => {
    setAuditLoading(true);
    setAuditError(false);
    try {
      const data = await apiGet<AuditLog[]>("/api/v1/audit/logs?limit=20");
      setAuditLogs(data);
    } catch {
      setAuditError(true);
    } finally {
      setAuditLoading(false);
    }
  }, []);

  const fetchTradingMode = useCallback(async () => {
    setTradingModeLoading(true);
    try {
      const data = await apiGet<TradingModeSetting>("/api/v1/settings/trading_mode");
      setTradingMode(data.trading_mode);
    } catch {
      // 조회 실패 시 null 유지
    } finally {
      setTradingModeLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRisk();
    fetchTrading();
    fetchAuditLogs();
    fetchTradingMode();
  }, [fetchRisk, fetchTrading, fetchAuditLogs, fetchTradingMode]);

  // 리스크 장중 잠금 여부: market_hours=true 이고 risk_lock_during_trading 설정이 "true"일 때
  const riskLockSetting = riskSettings?.find(
    (s) => s.key === "risk_lock_during_trading"
  );
  const isRiskLocked = marketHours && riskLockSetting?.value === "true";

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-lg font-semibold tracking-tight">설정</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">
          거래 모드 및 리스크/매매 설정 관리
        </p>
      </div>

      {/* Section 1: 거래 모드 */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight">거래 모드</h2>
        <div
          className={cn(
            "rounded-lg border border-border/50 bg-card p-4",
            user?.trading_env === "live"
              ? "border-red-600/40"
              : "border-green-700/40"
          )}
        >
          {user ? (
            <ModeSwitch
              currentEnv={user.trading_env}
              onSuccess={() => window.location.reload()}
            />
          ) : (
            <Skeleton className="h-8 w-48" />
          )}
        </div>
      </div>

      {/* Section 2: 매매 모드 */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight">매매 모드</h2>
        <div className="rounded-lg border border-border/50 bg-card p-4">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
                현재 모드
              </span>
              <ModeIndicator />
            </div>
            {tradingModeLoading ? (
              <Skeleton className="h-8 w-36" />
            ) : (
              <TradingModeSwitch
                currentMode={tradingMode ?? "manual"}
                onSuccess={fetchTradingMode}
              />
            )}
          </div>
        </div>
      </div>

      {/* Section 3: 리스크 설정 */}
      <SettingsTable
        title="리스크 설정"
        settings={riskSettings}
        isLoading={riskLoading}
        error={riskError}
        marketLocked={!!isRiskLocked}
        onRefresh={fetchRisk}
      />

      {/* Section 4: 매매 설정 */}
      <SettingsTable
        title="매매 설정"
        settings={tradingSettings}
        isLoading={tradingLoading}
        error={tradingError}
        marketLocked={false}
        onRefresh={fetchTrading}
      />

      {/* Section 5: 감사 로그 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">감사 로그</h2>
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-xs font-mono px-2"
            onClick={fetchAuditLogs}
            disabled={auditLoading}
          >
            새로고침
          </Button>
        </div>
        {auditError && (
          <p className="text-xs font-mono text-destructive">⚠ 데이터를 불러올 수 없습니다</p>
        )}
        <div className="rounded-lg border border-border/50 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border/50">
                {["시각", "액션", "대상", "이전값", "새값", "사용자"].map((h) => (
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
              {auditLoading &&
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i} className="border-border/30">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 w-20" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              {!auditLoading && auditLogs?.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center py-8 text-xs font-mono text-muted-foreground"
                  >
                    감사 로그 없음
                  </TableCell>
                </TableRow>
              )}
              {auditLogs?.map((log) => (
                <TableRow key={log.id} className="border-border/30 hover:bg-accent/30">
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {formatDateTime(log.created_at)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className="text-[10px] font-mono px-1.5 py-0"
                    >
                      {log.action}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{log.target_key}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {log.old_value ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {log.new_value ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {log.actor}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
