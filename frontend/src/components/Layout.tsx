import { useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { SpinnerIcon } from "@/ui/icons";

export function Layout() {
  const { user, loading } = useAuthContext();
  const [mobileOpen, setMobileOpen] = useState(false);

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
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
