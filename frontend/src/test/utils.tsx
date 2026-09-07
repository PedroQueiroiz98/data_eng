import type { ReactElement, ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/components/AuthProvider";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ConfirmProvider } from "@/ui/ConfirmDialog";
import { ToastProvider } from "@/ui/Toast";

export function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

interface Options extends Omit<RenderOptions, "wrapper"> {
  route?: string;
  /** quando setado, o ui é montado em <Route path={path}> (para useParams) */
  path?: string;
  withAuth?: boolean;
}

export function renderWithProviders(ui: ReactElement, opts: Options = {}) {
  const { route = "/", path, withAuth = false, ...rest } = opts;
  const qc = makeQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    const inner = path ? (
      <Routes>
        <Route path={path} element={children} />
      </Routes>
    ) : (
      children
    );
    const tree = (
      <ThemeProvider>
        <QueryClientProvider client={qc}>
          <ToastProvider>
            <ConfirmProvider>
              <MemoryRouter initialEntries={[route]}>{inner}</MemoryRouter>
            </ConfirmProvider>
          </ToastProvider>
        </QueryClientProvider>
      </ThemeProvider>
    );
    return withAuth ? <AuthProvider>{tree}</AuthProvider> : tree;
  }

  return { qc, ...render(ui, { wrapper: Wrapper, ...rest }) };
}
