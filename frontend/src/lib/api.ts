const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function resolveUrl(path: string): string {
  if (path.startsWith("/api") || path.startsWith("/ready") || path.startsWith("/health")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

interface ErrorBody {
  error?: { code?: string; message?: string };
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = resolveUrl(path);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);

  if (res.status === 401 && !path.startsWith("/auth/login")) {
    window.dispatchEvent(new CustomEvent("nbp:unauthorized"));
  }
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const parsed = text ? (JSON.parse(text) as unknown) : null;

  if (!res.ok) {
    const errBody = parsed as ErrorBody | null;
    throw new ApiError(
      errBody?.error?.message ?? `${method} ${url} → ${res.status}`,
      res.status,
      errBody?.error?.code,
    );
  }
  return parsed as T;
}

export const apiGet = <T>(path: string): Promise<T> => request<T>("GET", path);
export const apiPost = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>("POST", path, body);
export const apiPut = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>("PUT", path, body);
export const apiPatch = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>("PATCH", path, body);
export const apiDelete = (path: string): Promise<void> => request<void>("DELETE", path);

export interface ReadinessCheck {
  ok: boolean;
  detail: string | null;
}

export interface Readiness {
  status: "ok" | "degraded";
  checks: Record<string, ReadinessCheck>;
}

/**
 * `/ready` responde 503 quando degradado, mas com corpo JSON válido — que
 * queremos exibir. Por isso não passa pelo `request` (que lança em não-2xx).
 */
export async function fetchReadiness(): Promise<Readiness> {
  const res = await fetch(resolveUrl("/ready"), { headers: { Accept: "application/json" } });
  return (await res.json()) as Readiness;
}
