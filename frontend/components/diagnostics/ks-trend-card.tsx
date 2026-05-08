"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { KSTrendPoint } from "@/lib/api";
import { cn } from "@/lib/utils";

const TIERS = ["gap_open", "prev_high", "prev_close", "volume_surge"] as const;

const TIER_COLORS: Record<string, string> = {
  gap_open: "bg-orange-500/70",
  prev_high: "bg-emerald-500/70",
  prev_close: "bg-sky-500/70",
  volume_surge: "bg-violet-500/70",
};

const TIER_TEXT_COLORS: Record<string, string> = {
  gap_open: "text-orange-400",
  prev_high: "text-emerald-400",
  prev_close: "text-sky-400",
  volume_surge: "text-violet-400",
};

/** KS 시계열 7주 라인 — SVG inline, 0.05 임계 표시 */
function KsSparkline({
  points,
  tier,
}: {
  points: KSTrendPoint[];
  tier: string;
}) {
  if (points.length === 0) {
    return (
      <p className="text-[11px] font-mono text-muted-foreground">데이터 없음</p>
    );
  }

  const W = 280;
  const H = 48;
  const THRESHOLD = 0.05;

  const sorted = [...points].sort(
    (a, b) =>
      new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
  );

  const minY = 0;
  const maxY = Math.max(1, ...sorted.map((p) => p.ks_pvalue));

  const toX = (i: number) =>
    sorted.length > 1 ? (i / (sorted.length - 1)) * W : W / 2;
  const toY = (v: number) => H - ((v - minY) / (maxY - minY)) * H;

  // threshold Y 좌표
  const thresholdY = toY(THRESHOLD);

  const pathD = sorted
    .map((p, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(p.ks_pvalue).toFixed(1)}`)
    .join(" ");

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full overflow-visible"
      aria-label={`${tier} KS p-value 추세`}
    >
      {/* 임계선 0.05 — 빨간 점선 */}
      {thresholdY >= 0 && thresholdY <= H && (
        <>
          <line
            x1={0}
            y1={thresholdY}
            x2={W}
            y2={thresholdY}
            stroke="#ef4444"
            strokeWidth={1}
            strokeDasharray="4 3"
            opacity={0.7}
          />
          <text
            x={W - 2}
            y={thresholdY - 3}
            textAnchor="end"
            className="text-[9px] fill-red-400 font-mono"
            fontSize={8}
            fill="#f87171"
          >
            0.05
          </text>
        </>
      )}

      {/* 라인 */}
      <path
        d={pathD}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        className={TIER_TEXT_COLORS[tier] ?? "text-muted-foreground"}
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* 포인트 */}
      {sorted.map((p, i) => {
        const cx = toX(i);
        const cy = toY(p.ks_pvalue);
        const isCritical = p.ks_pvalue < THRESHOLD;
        return (
          <circle
            key={p.recorded_at}
            cx={cx}
            cy={cy}
            r={isCritical ? 3.5 : 2}
            fill={isCritical ? "#ef4444" : "currentColor"}
            className={
              isCritical
                ? "fill-red-500"
                : (TIER_TEXT_COLORS[tier] ?? "text-muted-foreground")
            }
          />
        );
      })}
    </svg>
  );
}

interface Props {
  points: KSTrendPoint[];
}

export function KsTrendCard({ points }: Props) {
  // tier별 분리
  const byTier = new Map<string, KSTrendPoint[]>();
  for (const tier of TIERS) {
    byTier.set(
      tier,
      points.filter((p) => p.tier === tier)
    );
  }

  // 전체 critical 개수 (p < 0.05)
  const criticalCount = points.filter((p) => p.ks_pvalue < 0.05).length;

  return (
    <Card
      className={cn(
        "transition-colors",
        criticalCount > 0 ? "border-red-500/50" : "border-border"
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-mono text-sm">
          시뮬-실측 KS 검정 7주 이동
          {criticalCount > 0 && (
            <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-mono text-red-300">
              드리프트 {criticalCount}건
            </span>
          )}
        </CardTitle>
        <CardDescription className="font-mono text-[11px]">
          tier별 KS p-value 시계열 · 빨간 점선 = 0.05 임계 · p &lt; 0.05 포인트 빨간 강조
        </CardDescription>
      </CardHeader>
      <CardContent>
        {points.length === 0 ? (
          <p className="text-xs font-mono text-muted-foreground">
            데이터 없음 — 백테스트 실행 후 표시됩니다
          </p>
        ) : (
          <div className="space-y-5">
            {TIERS.map((tier) => {
              const tierPoints = byTier.get(tier) ?? [];
              const latestP = tierPoints.at(-1)?.ks_pvalue ?? null;
              return (
                <div key={tier} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-block h-2 w-2 rounded-full",
                        TIER_COLORS[tier]
                      )}
                    />
                    <span
                      className={cn(
                        "text-[11px] font-mono",
                        TIER_TEXT_COLORS[tier]
                      )}
                    >
                      {tier}
                    </span>
                    {latestP !== null && (
                      <span
                        className={cn(
                          "ml-auto text-[10px] font-mono tabular-nums",
                          latestP < 0.05
                            ? "text-red-400 font-semibold"
                            : "text-muted-foreground"
                        )}
                      >
                        최신 p={latestP.toFixed(3)}
                        {latestP < 0.05 && " ⚠"}
                      </span>
                    )}
                  </div>
                  <div className="pl-4">
                    <KsSparkline points={tierPoints} tier={tier} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
