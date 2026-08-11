import type { LoginResponse } from './types/auth';

const TOKEN_KEY = 'review-monitoring.access-token';
const USER_KEY = 'review-monitoring.user';

export function getToken(): string | null { return localStorage.getItem(TOKEN_KEY); }
export function saveSession(session: LoginResponse): void {
  localStorage.setItem(TOKEN_KEY, session.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(session));
}
export function clearSession(): void { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
export function isAuthenticated(): boolean { return Boolean(getToken()); }
export function getSession(): LoginResponse | null {
  try { const value = localStorage.getItem(USER_KEY); return value ? JSON.parse(value) as LoginResponse : null; }
  catch { return null; }
}
