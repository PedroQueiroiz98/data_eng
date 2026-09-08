import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { ProviderDrawer } from "@/components/notifications/ProviderDrawer";
import type { NotificationProvider } from "@/lib/notificationProviders";

afterEach(() => vi.restoreAllMocks());

function captureFetch() {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ url, method, body });
    return Promise.resolve(
      new Response(JSON.stringify({ id: "new", ...(body as object) }), { status: 201 }),
    );
  });
  return calls;
}

describe("ProviderDrawer", () => {
  it("cria um provider Bitrix com o body esperado", async () => {
    const calls = captureFetch();
    renderWithProviders(<ProviderDrawer open provider={null} onClose={() => {}} />);

    await userEvent.type(screen.getByLabelText(/Nome/), "Bitrix Ops");
    await userEvent.click(screen.getByRole("tab", { name: "Configuração" }));
    await userEvent.type(screen.getByLabelText(/URL do Bitrix/), "https://empresa.bitrix24.com.br");
    await userEvent.type(screen.getByLabelText(/Dialog ID/), "chat3129");
    await userEvent.type(screen.getByLabelText(/Token/i), "secret-token");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST");
      expect(post).toBeTruthy();
      expect(post!.url).toContain("/notifications/providers");
      expect(post!.body).toMatchObject({
        name: "Bitrix Ops",
        provider_type: "BITRIX",
        enabled: true,
        configuration: { url: "https://empresa.bitrix24.com.br", dialog_id: "chat3129" },
        secret: "secret-token",
      });
    });
  });

  it("ao editar, salvar sem tocar na senha mantém a máscara ******** como secret", async () => {
    const calls = captureFetch();
    const provider: NotificationProvider = {
      id: "p9",
      name: "E-mail Ops",
      description: null,
      provider_type: "EMAIL",
      enabled: true,
      configuration: {
        host: "smtp.x.com",
        port: 587,
        from_email: "no@x.com",
        recipients: ["a@x.com"],
        cc: [],
        bcc: [],
        use_tls: true,
      },
      has_password: true,
      has_credential: false,
      summary: "smtp.x.com:587 · 1 destinatário(s)",
      created_at: "2026-09-07T10:00:00Z",
      updated_at: "2026-09-07T10:00:00Z",
    };
    renderWithProviders(<ProviderDrawer open provider={provider} onClose={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => {
      const put = calls.find((c) => c.method === "PUT");
      expect(put).toBeTruthy();
      expect((put!.body as { secret: string }).secret).toBe("********");
    });
  });
});
