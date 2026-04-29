export const TOKEN_COOKIE = "stockbot_token";

const COOKIE_MAX_AGE = 86400;

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_COOKIE);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_COOKIE, token);
  document.cookie = `${TOKEN_COOKIE}=${token}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_COOKIE);
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0`;
}

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getToken();
  const headers = new Headers(options.headers);

  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const resp = await fetch(path, { ...options, headers });

  if (resp.status === 401 && window.location.pathname !== "/login") {
    removeToken();
    window.location.href = "/login";
  }

  return resp;
}

export async function apiGet<T>(path: string): Promise<T> {
  const resp = await apiFetch(path);
  if (!resp.ok) throw new Error(`GET ${path} failed: ${resp.status}`);
  return resp.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const resp = await apiFetch(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`POST ${path} failed: ${resp.status}`);
  return resp.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const resp = await apiFetch(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`PUT ${path} failed: ${resp.status}`);
  return resp.json() as Promise<T>;
}

// === Phase 8.5 Sprint 1: 관측성 metrics API ===

export interface ScoreBucketStat {
  bucket: string;
  count_today: number;
  count_7d_avg: number;
}

export interface ScoreHistogramResponse {
  date: string;
  buckets: ScoreBucketStat[];
}

export interface StageHeatmapCell {
  stage: string;
  hour_min: string;
  count: number;
}

export interface StageHeatmapResponse {
  date: string;
  cells: StageHeatmapCell[];
}

export interface TopRejectItem {
  recorded_at: string | null;
  stage: string;
  stock_code: string | null;
  breakout_ref: number | null;
  current_price: number | null;
  detail: Record<string, unknown> | null;
}

export interface TopRejectsResponse {
  items: TopRejectItem[];
}

export interface VirtualSignalItem {
  id: number;
  observed_at: string;
  stock_code: string;
  stock_name: string | null;
  virtual_stage: string;
  breakout_ref: number | null;
  current_price: number | null;
  gap_rate: number | null;
  prev_close: number | null;
  would_execute: boolean;
  detail: Record<string, unknown> | null;
}

export interface VirtualSignalsResponse {
  items: VirtualSignalItem[];
}

export interface ShadowStageCell {
  stage: string;
  hour_min: string;
  pass_count: number;
  fail_count: number;
  pass_rate: number | null;
}

export interface ShadowHeatmapResponse {
  date: string;
  stages: string[];
  cells: ShadowStageCell[];
}

// === Phase 8.5 Sprint 2: 폴백 발동 통계 ===

export interface FallbackStats {
  date: string;
  triggered_count: number;
  codes: string[];
}

// === Phase 8.5 Sprint 2.5: 자동 롤백 발동 상태 ===

export interface OverrideStatus {
  is_active: boolean;
  triggered_at: string | null;
  reason: string | null;
  affected_keys: string[];
}

// === Phase 8.6 Sprint 1: M-F2 (G1) + R1~R4 다중 트리거 ===

export interface FallbackSignalRate {
  date: string;
  fallback_signals: number;
  fallback_triggered_codes: number;
  rate: number | null;
}

export interface Phase86Status {
  rollback_active: boolean;
  circuit_breaker_active: boolean;
  fallback_share: number | null;
  fallback_signals: number;
  primary_candidates: number;
}

export interface TierCorrelationResponse {
  window_days: number;
  phi: Record<string, number>;
  cond_prob: Record<string, number>;
  max_phi: number;
  max_cond: number;
  phi_threshold: number;
  cond_threshold: number;
  ok: boolean;
}

export interface TierPassRateBucket {
  date: string;
  gap_open: number;
  prev_high: number;
  prev_close: number;
}

export interface TierPassRateResponse {
  window_days: number;
  buckets: TierPassRateBucket[];
}

export interface SimVsRealDiffBucket {
  date: string;
  diff: number;
}

export interface SimVsRealDiffResponse {
  window_days: number;
  threshold: number;
  buckets: SimVsRealDiffBucket[];
  ok: boolean;
}

export const metricsPaths = {
  scoreHistogram: (days = 7) => `/api/v1/metrics/score-histogram?days=${days}`,
  stageHeatmap: (date = "today") =>
    `/api/v1/metrics/stage-heatmap?date=${encodeURIComponent(date)}`,
  topRejects: (limit = 5) => `/api/v1/metrics/top-rejects?limit=${limit}`,
  virtualSignals: (days = 7) => `/api/v1/metrics/virtual-signals?days=${days}`,
  shadowHeatmap: (date = "today") =>
    `/api/v1/metrics/shadow-heatmap?date=${encodeURIComponent(date)}`,
  fallbackStats: (date = "today") =>
    `/api/v1/metrics/fallback-stats?date=${encodeURIComponent(date)}`,
  overrideStatus: () => `/api/v1/metrics/override-status`,
  fallbackSignalRate: (date = "today") =>
    `/api/v1/metrics/fallback-signal-rate?date=${encodeURIComponent(date)}`,
  phase86Status: () => `/api/v1/metrics/phase86-status`,
  tierCorrelation: (days = 7) =>
    `/api/v1/metrics/tier-correlation?days=${days}`,
  tierPassRate: (days = 7) => `/api/v1/metrics/tier-pass-rate?days=${days}`,
  simVsRealDiff: (days = 7) => `/api/v1/metrics/sim-vs-real-diff?days=${days}`,
};

/**
 * 자동 롤백 발동 상태 조회 (Phase 8.5 Sprint 2.5).
 * OverrideBanner / FallbackStatsCard 등에서 공유.
 */
export async function fetchOverrideStatus(): Promise<OverrideStatus> {
  return apiGet<OverrideStatus>(metricsPaths.overrideStatus());
}

/**
 * 리스크 일일 카운터 리셋. 백엔드는 리셋 후 최신 risk_status dict를 반환한다.
 * 실패 시 apiPost가 throw하므로, 이 함수가 resolve되면 성공으로 간주한다.
 */
export async function resetRiskCounters(): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    "/api/v1/trading/risk/reset",
    {}
  );
}
