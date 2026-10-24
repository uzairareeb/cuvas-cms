// MY CUVAS API client — the ONLY way the frontend talks to Flask.
//
// All calls use same-origin relative /api/v1 paths: the Next.js
// rewrites (next.config.mjs) proxy them server-side to the Flask
// project, so the Flask session cookie is set/sent first-party —
// no CORS, no tokens, no absolute URLs, no secrets in this code.
//
// Every request carries "X-Requested-With: XMLHttpRequest": Flask's
// CSRF guard for /api/v1 mutations requires it (plan §2.2 point 6).
// Responses use the envelope {ok:true, data} / {ok:false, error}.

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export interface ApiUser {
  id: number;
  username: string;
  role: string;
  name: string;
}

export interface SessionInfo {
  user: ApiUser;
  home: string;
}

export interface LoginResult extends SessionInfo {}

export interface DashboardData {
  kpis: {
    total_students: number;
    active_faculty: number;
    pending_vouchers: number;
    total_outstanding: number;
  };
  students_by_program: { name: string; count: number }[];
  students_by_session: { name: string; count: number }[];
  pending_approvals: {
    key: string;
    label: string;
    count: number;
    href: string;
  }[];
  pending_vouchers: {
    challan_no: string;
    student_name: string;
    amount: number;
    status: string;
  }[];
  recent_students: {
    reg_no: string;
    name: string;
    program: string | null;
    status: string | null;
  }[];
  recent_notifications: { title: string; created_at: string | null }[];
  recent_activity: {
    action: string;
    detail: string | null;
    created_at: string | null;
  }[];
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        ...(options.headers || {}),
      },
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server.");
  }
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    /* non-JSON body — handled below */
  }
  const env = body as
    | { ok: true; data: T }
    | { ok: false; error: { code: string; message: string } }
    | null;
  if (env && env.ok === true) {
    return env.data;
  }
  if (env && env.ok === false) {
    throw new ApiError(resp.status, env.error.code, env.error.message);
  }
  throw new ApiError(
    resp.status,
    "bad_response",
    "The server returned an unexpected response."
  );
}

export function login(username: string, password: string) {
  return request<LoginResult>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout() {
  return request<Record<string, never>>("/api/v1/auth/logout", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function me() {
  return request<SessionInfo>("/api/v1/auth/me");
}

export function adminDashboard() {
  return request<DashboardData>("/api/v1/admin/dashboard");
}
