const TOKEN_KEY = "training_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  const t = getToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(`/api/v1${path}`, { ...opts, headers });
  if (res.status === 401) {
    setToken(null);
    throw new ApiError(401, "Not authenticated");
  }
  if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
  if (res.status === 204) return null as T;
  return (await res.json()) as T;
}

/** Today's date as YYYY-MM-DD in the *local* timezone.
 * (Date.toISOString() is UTC, which rolls a day early/late for non-UTC users.) */
export const todayLocal = (): string => {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
};

/** Shift a YYYY-MM-DD day string by `delta` days, staying in local time. */
export const shiftDay = (day: string, delta: number): string => {
  const [y, m, d] = day.split("-").map(Number);
  const dt = new Date(y, m - 1, d + delta);
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${dt.getFullYear()}-${mm}-${dd}`;
};

/** Long weekday name ("Monday") for a YYYY-MM-DD day string (local). */
export const weekdayOf = (day: string): string => {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "long" });
};

export const get = <T>(p: string) => api<T>(p);
export const post = <T>(p: string, body?: unknown) =>
  api<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
export const patch = <T>(p: string, body: unknown) =>
  api<T>(p, { method: "PATCH", body: JSON.stringify(body) });
export const put = <T>(p: string, body: unknown) =>
  api<T>(p, { method: "PUT", body: JSON.stringify(body) });
export const del = (p: string) => api(p, { method: "DELETE" });
