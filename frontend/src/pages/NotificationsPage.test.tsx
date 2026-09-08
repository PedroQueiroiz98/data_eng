import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { NotificationsPage } from "@/pages/NotificationsPage";

const mockAuth = vi.fn(() => ({ user: { role: "admin" } }));
vi.mock("@/components/AuthProvider", () => ({
  useAuthContext: () => mockAuth(),
}));

function mockFetch(providers: unknown[]) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/notifications/providers")) {
      return Promise.resolve(new Response(JSON.stringify(providers), { status: 200 }));
    }
    if (url.includes("/notifications/deliveries")) {
      return Promise.resolve(
        new Response(JSON.stringify({ items: [], total: 0, limit: 100, offset: 0 }), {
          status: 200,
        }),
      );
    }
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  mockAuth.mockReturnValue({ user: { role: "admin" } });
});

describe("NotificationsPage", () => {
  it("lista provedores e alterna abas", async () => {
    mockFetch([
      {
        id: "p1",
        name: "Bitrix Corporativo",
        description: null,
        provider_type: "BITRIX",
        enabled: true,
        configuration: { dialog_id: "chat3129" },
        has_password: false,
        has_credential: true,
        summary: "canal chat3129",
        created_at: "2026-09-07T10:00:00Z",
        updated_at: "2026-09-07T10:00:00Z",
      },
    ]);
    renderWithProviders(<NotificationsPage />);
    expect(await screen.findByText("Bitrix Corporativo")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Histórico de envios" }));
    expect(await screen.findByText("Nenhum envio registrado")).toBeInTheDocument();
  });

  it("mostra empty state quando não há provedores", async () => {
    mockFetch([]);
    renderWithProviders(<NotificationsPage />);
    expect(
      await screen.findByText("Nenhum serviço de notificação configurado"),
    ).toBeInTheDocument();
  });

  it("esconde 'Adicionar provedor' para não-admin", async () => {
    mockAuth.mockReturnValue({ user: { role: "member" } });
    mockFetch([]);
    renderWithProviders(<NotificationsPage />);
    await screen.findByText("Nenhum serviço de notificação configurado");
    expect(
      screen.queryByRole("button", { name: /Adicionar provedor/ }),
    ).not.toBeInTheDocument();
  });
});
