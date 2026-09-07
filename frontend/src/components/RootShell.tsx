import { Outlet } from "react-router-dom";
import { AuthProvider } from "@/components/AuthProvider";

export function RootShell() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}
