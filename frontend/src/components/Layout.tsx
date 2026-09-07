import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import { Sidebar } from "@/components/Sidebar";

export function Layout() {
  const { user, loading } = useAuthContext();

  if (loading) {
    return <div className="p-8 text-slate-500">Carregando…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex min-h-screen bg-white text-slate-900">
      <Sidebar />
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}
