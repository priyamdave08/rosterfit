// Thin typed client for the RosterFit API. Errors carry the server's own message so the
// UI can say what went wrong and what to do, instead of a generic failure.

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** A sleeping or starting API answers with a network failure or a 502/503/504 until it is up. */
export function isWakingError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 0 || error.status === 502 || error.status === 503 || error.status === 504);
}

/** Retry policy shared by every query: keep trying for about three minutes while the API wakes. */
export const WAKE_RETRIES = 36;
export const WAKE_DELAY_MS = 5000;
export const retryWhileWaking = (failureCount: number, error: unknown): boolean =>
  isWakingError(error) ? failureCount < WAKE_RETRIES : failureCount < 1;
export const wakeDelay = (attempt: number, error: unknown): number =>
  isWakingError(error) ? WAKE_DELAY_MS : Math.min(1000 * 2 ** attempt, 8000);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "Can't reach the RosterFit engine. Check your connection, or wait a minute if it is waking up, then retry.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

export function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== "")
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  return request<T>(`${path}${qs === "?" ? "" : qs}`);
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
