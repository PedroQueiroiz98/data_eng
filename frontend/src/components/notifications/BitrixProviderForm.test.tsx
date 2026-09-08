import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import {
  BitrixProviderForm,
  bitrixConfigFromState,
  bitrixStateFromConfig,
  EMPTY_BITRIX,
} from "@/components/notifications/BitrixProviderForm";
import { SECRET_MASK } from "@/lib/notificationProviders";

describe("BitrixProviderForm", () => {
  it("hidrata do config e mascara o token quando has_credential", () => {
    const s = bitrixStateFromConfig(
      { url: "https://b24", dialog_id: "chat1", bot_id: "93" },
      true,
    );
    expect(s.token).toBe(SECRET_MASK);
    expect(s.url).toBe("https://b24");
    expect(s.dialog_id).toBe("chat1");
  });

  it("monta o payload de configuração e o secret", () => {
    const { configuration, secret } = bitrixConfigFromState({
      ...EMPTY_BITRIX,
      url: " https://b24 ",
      dialog_id: " chat9 ",
      token: "tok",
    });
    expect(configuration).toMatchObject({ url: "https://b24", dialog_id: "chat9" });
    expect(secret).toBe("tok");
  });

  it("token começa oculto e o botão mostra/oculta alterna o input", async () => {
    render(<BitrixProviderForm value={{ ...EMPTY_BITRIX, token: "abc" }} onChange={() => {}} />);
    const input = screen.getByLabelText(/Token/i) as HTMLInputElement;
    expect(input.type).toBe("password");
    await userEvent.click(screen.getByRole("button", { name: "Mostrar" }));
    expect((screen.getByLabelText(/Token/i) as HTMLInputElement).type).toBe("text");
  });
});
