const TOKEN_KEY = "stockbot_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
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

  if (resp.status === 401) {
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
