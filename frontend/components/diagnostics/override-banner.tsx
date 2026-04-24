"use client";

import { usePolling } from "@/lib/hooks/use-polling";
import { metricsPaths, OverrideStatus } from "@/lib/api";

/**
 * Phase 8.5 Sprint 2.5 — 자동 롤백 발동 경고 배너.
 *
 * `/api/v1/metrics/override-status`를 60초 주기로 폴링하여
 * `is_active=true`인 경우에만 주황색 경고 배너를 표시한다.
 * 색상은 amber 계열만 사용 (한국 증시 빨강/초록 금지).
 */
export function OverrideBanner() {
  const { data } = usePolling<OverrideStatus>(
    metricsPaths.overrideStatus(),
    60_000
  );

  if (!data?.is_active) return null;

  return (
    <div
      role="alert"
      className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-amber-900 dark:text-amber-200"
    >
      <div className="flex items-start gap-2">
        <span aria-hidden className="text-lg">⚠️</span>
        <div className="text-sm">
          <p className="font-semibold">자동 롤백 발동 중</p>
          <p className="mt-1">
            사유: <code className="font-mono">{data.reason ?? "unknown"}</code>
            {" · "}발동 시각: {data.triggered_at ?? "-"} (KST)
          </p>
          <p className="mt-1 text-xs opacity-80">
            관리자 확인 후 Redis key(`settings:override:*`) 수동 삭제 필요.
          </p>
        </div>
      </div>
    </div>
  );
}
