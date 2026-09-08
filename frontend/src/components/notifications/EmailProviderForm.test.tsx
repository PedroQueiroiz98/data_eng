import { describe, expect, it } from "vitest";
import {
  emailConfigFromState,
  emailStateFromConfig,
  EMPTY_EMAIL,
} from "@/components/notifications/EmailProviderForm";
import { SECRET_MASK } from "@/lib/notificationProviders";

describe("EmailProviderForm helpers", () => {
  it("converte destinatários/cc/bcc de texto para lista e porta para número", () => {
    const { configuration, secret } = emailConfigFromState({
      ...EMPTY_EMAIL,
      host: "smtp.x.com",
      port: "465",
      from_email: "no@x.com",
      recipients: "a@x.com\nb@x.com, c@x.com",
      cc: "d@x.com",
      bcc: "",
      password: "novo",
    });
    expect(configuration.port).toBe(465);
    expect(configuration.recipients).toEqual(["a@x.com", "b@x.com", "c@x.com"]);
    expect(configuration.cc).toEqual(["d@x.com"]);
    expect(configuration.bcc).toEqual([]);
    expect(secret).toBe("novo");
  });

  it("hidrata do config e marca a senha como ******** quando has_password", () => {
    const s = emailStateFromConfig(
      { host: "smtp", port: 587, recipients: ["a@x.com"], from_email: "f@x.com" },
      true,
    );
    expect(s.password).toBe(SECRET_MASK);
    expect(s.recipients).toBe("a@x.com");
    expect(s.host).toBe("smtp");
  });

  it("sem has_password a senha fica vazia (nunca expõe valor real)", () => {
    const s = emailStateFromConfig({ host: "smtp" }, false);
    expect(s.password).toBe("");
  });
});
