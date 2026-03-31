"use client";

import { useState } from "react";
import { usePolling } from "@/lib/hooks/use-polling";
import { apiPost } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface ScreeningResult {
  id: number;
  stock_code: string;
  rank?: number;
  score: number;
  is_hot?: boolean;
  status?: string;
  factors?: Record<string, unknown>;
  screened_at?: string | null;
}

type TabKey = "primary" | "secondary";

const TABS: { key: TabKey; label: string }[] = [
  { key: "primary", label: "1차 스크리닝" },
  { key: "secondary", label: "2차 스크리닝" },
];

const TRIGGER_LABELS: Record<TabKey, string> = {
  primary: "1차 트리거",
  secondary: "2차 트리거",
};

const TRIGGER_PATHS: Record<TabKey, string> = {
  primary: "/api/v1/screening/trigger/primary",
  secondary: "/api/v1/screening/trigger/secondary",
};

const DATA_PATHS: Record<TabKey, string> = {
  primary: "/api/v1/screening/primary",
  secondary: "/api/v1/screening/secondary",
};

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

interface ScreeningTableProps {
  tab: TabKey;
}

function ScreeningTable({ tab }: ScreeningTableProps) {
  const [triggering, setTriggering] = useState(false);

  const { data: results, isLoading, error } = usePolling<ScreeningResult[]>(
    DATA_PATHS[tab],
    5000
  );

  async function handleTrigger() {
    setTriggering(true);
    try {
      await apiPost(TRIGGER_PATHS[tab], {});
    } catch {
      // 오류는 무시하고 폴링으로 갱신
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {!isLoading && results && (
            <Badge
              variant="outline"
              className="text-[10px] font-mono px-2 py-0.5 text-muted-foreground border-border/50"
            >
              총 {results.length}건
            </Badge>
          )}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={handleTrigger}
          disabled={triggering}
          className="text-xs font-mono h-7 px-3 border-border/50"
        >
          {triggering ? "실행 중…" : TRIGGER_LABELS[tab]}
        </Button>
      </div>

      {error && (
        <p className="text-xs font-mono text-destructive">⚠ 데이터를 불러올 수 없습니다</p>
      )}

      <div className="rounded-lg border border-border/50 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/50">
              {["순위", "종목코드", "점수", "핫", "상태", "스크리닝 시각", "factors"].map((h) => (
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
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-14" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            {!isLoading && (!results || results.length === 0) && (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="text-center py-12 text-xs font-mono text-muted-foreground"
                >
                  스크리닝 결과가 없습니다
                </TableCell>
              </TableRow>
            )}
            {results?.map((item) => (
              <TableRow key={item.id} className="border-border/30 hover:bg-accent/30">
                <TableCell className="font-mono tabular-nums text-sm text-muted-foreground">
                  {item.rank ?? "—"}
                </TableCell>
                <TableCell>
                  <span className="font-mono font-medium text-sm">{item.stock_code}</span>
                </TableCell>
                <TableCell className="font-mono tabular-nums text-sm">
                  {typeof item.score === "number" ? item.score.toFixed(2) : "—"}
                </TableCell>
                <TableCell className="text-sm">
                  {item.is_hot ? "🔥" : "—"}
                </TableCell>
                <TableCell>
                  {item.status ? (
                    <Badge
                      variant="outline"
                      className="text-[10px] font-mono px-1.5 py-0 border-border/40 text-muted-foreground"
                    >
                      {item.status}
                    </Badge>
                  ) : (
                    <span className="text-xs font-mono text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {formatDateTime(item.screened_at)}
                </TableCell>
                <TableCell>
                  {item.factors && Object.keys(item.factors).length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(item.factors).map(([k, v]) => (
                        <Badge
                          key={k}
                          variant="outline"
                          className="text-[9px] font-mono px-1 py-0 border-border/40 text-muted-foreground"
                        >
                          {k}={String(v)}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs font-mono text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export default function ScreeningPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("primary");

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">스크리닝</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">
          종목 스크리닝 결과
        </p>
      </div>

      {/* 탭 */}
      <div className="flex gap-1 border-b border-border/40">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={cn(
              "px-4 py-2 text-xs font-mono transition-colors",
              "hover:text-foreground",
              activeTab === key
                ? "text-foreground border-b-2 border-primary -mb-px"
                : "text-muted-foreground border-b-2 border-transparent"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <ScreeningTable key={activeTab} tab={activeTab} />
    </div>
  );
}
