import { useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { useWorkspaceEvents } from "@/hooks/useWorkspaceEvents";
import { SpinnerIcon } from "@/ui/icons";

/**
 * Shell full-bleed para o Workspace (explorer | editor | painel).
 * Igual ao `Layout`, mas sem o `mx-auto max-w-6xl` e sem scroll no `<main>`
 * — a área do Workspace gerencia o próprio layout de 3 painéis.
 */
export function WorkspaceLayout() {
  const { user, loading } = useAuthContext();
  const [mobileOpen, setMobileOpen] = useState(false);
  useWorkspaceEvents();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-fg-faint">
        <SpinnerIcon className="h-6 w-6 animate-spin" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="flex h-full bg-surface-variant text-fg">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenu={() => setMobileOpen(true)} />
        <main className="flex min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
