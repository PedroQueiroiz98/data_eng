import { createContext, useContext, type ReactNode } from "react";
import { useAuth } from "@/hooks/useAuth";
import type { User } from "@/lib/auth";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();
  return <Ctx.Provider value={auth}>{children}</Ctx.Provider>;
}

export function useAuthContext(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuthContext fora de AuthProvider");
  return ctx;
}
