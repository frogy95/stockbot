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

/**
 * Phase 8 Sprint 2: 리스크 일일 카운터 리셋 (Hotfix #153 API 소비)
 * 연속 손절 / 비상 정지 / 일일 거래 카운터를 초기화한다.
 */
export async function resetRiskCounters(): Promise<{
  ok: boolean;
  message?: string;
}> {
  return apiPost<{ ok: boolean; message?: string }>(
    "/api/v1/trading/risk/reset",
    {}
  );
}
