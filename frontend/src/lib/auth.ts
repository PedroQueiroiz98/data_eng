import { apiGet, apiPost, setAuthToken } from "@/lib/api";

const TOKEN_KEY = "nbp.token";

export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "member";
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export function loadToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode: mantém só em memória */
  }
  setAuthToken(token);
}

// aplica o token salvo assim que o módulo carrega
setAuthToken(loadToken());

export async function login(email: string, password: string): Promise<User> {
  const resp = await apiPost<LoginResponse>("/auth/login", { email, password });
  storeToken(resp.access_token);
  return resp.user;
}

export function logout(): void {
  storeToken(null);
}

export const getMe = (): Promise<User> => apiGet<User>("/auth/me");
