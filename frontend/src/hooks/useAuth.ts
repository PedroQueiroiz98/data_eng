import { useCallback, useEffect, useState } from "react";
import {
  getMe,
  loadToken,
  login as apiLogin,
  logout as apiLogout,
  type User,
} from "@/lib/auth";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const token = loadToken();
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) apiLogout();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      apiLogout();
      setUser(null);
    };
    window.addEventListener("nbp:unauthorized", onUnauthorized);
    return () => window.removeEventListener("nbp:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = await apiLogin(email, password);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
  }, []);

  return { user, loading, login, logout };
}
