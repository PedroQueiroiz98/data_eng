import { Outlet } from "react-router-dom";
import { AuthProvider } from "@/components/AuthProvider";
import { ConfirmProvider } from "@/ui/ConfirmDialog";
import { ToastProvider } from "@/ui/Toast";

export function RootShell() {
  return (
    <AuthProvider>
      <ToastProvider>
        <ConfirmProvider>
          <Outlet />
        </ConfirmProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
