// API client. The server address defaults to this page's origin (home computer serves both); a different
// address can be set in Status → Server when the app is hosted elsewhere (for example on Vercel).
const KEY_TOKEN = "cc:token", KEY_BASE = "cc:api";

function store(key: string, value?: string | null): string | null {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
  } catch { /* private mode: keep the session in memory only */ }
  return value ?? null;
}

export const apiBase = () => (store(KEY_BASE) || "").replace(/\/$/, "");
export const setApiBase = (url: string) => store(KEY_BASE, url.trim() || null);
export const token = () => store(KEY_TOKEN);
export class AuthError extends Error {}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const t = token();
  const res = await fetch(apiBase() + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}), ...(init.headers || {}) },
  });
  if (res.status === 401) { store(KEY_TOKEN, null); throw new AuthError((await res.json().catch(() => ({}))).detail || "Sign in"); }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `The server answered ${res.status}`);
  return res.json();
}

export async function login(password: string) {
  const r = await api<{ token: string }>("/api/login", { method: "POST", body: JSON.stringify({ password }) });
  store(KEY_TOKEN, r.token);
}

export async function logout() {
  try { await api("/api/logout", { method: "POST" }); } finally { store(KEY_TOKEN, null); }
}
