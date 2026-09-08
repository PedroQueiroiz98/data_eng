import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useCreateNotificationProvider,
  useToggleNotificationProvider,
} from "@/hooks/useNotificationProviders";

afterEach(() => vi.restoreAllMocks());

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useNotificationProviders mutations", () => {
  it("invalida a lista de provedores após criar", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "x" }), { status: 201 }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useCreateNotificationProvider(), {
      wrapper: wrapper(qc),
    });
    await result.current.mutateAsync({
      name: "n",
      description: null,
      provider_type: "EMAIL",
      enabled: true,
      configuration: {},
      secret: null,
    });
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ queryKey: ["notification-providers"] }),
    );
  });

  it("invalida a lista após toggle", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "x", enabled: false }), { status: 200 }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useToggleNotificationProvider(), {
      wrapper: wrapper(qc),
    });
    await result.current.mutateAsync({ id: "x", enabled: false });
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ queryKey: ["notification-providers"] }),
    );
  });
});
