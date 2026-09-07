import { useEffect, useState } from "react";
import {
  useNotificationSettings,
  useSaveNotificationSettings,
} from "@/hooks/useNotifications";
import { SECRET_MASK, type NotificationSettingsInput } from "@/lib/notifications";
import { Button, Card, Switch, TextField, useToast } from "@/ui";

const EMPTY: NotificationSettingsInput = {
  email_enabled: false,
  smtp_host: "",
  smtp_port: 587,
  smtp_username: "",
  smtp_from: "",
  smtp_use_tls: true,
  smtp_password: "",
  bitrix_enabled: false,
  bitrix_url: "",
  bitrix_send_message_path: "",
  bitrix_bot_id: "",
  bitrix_bot_token: "",
  default_on_failure: false,
  default_email_recipients: [],
  default_bitrix_dialog_id: "",
};

const linesToList = (s: string): string[] =>
  s
    .split(/[\n,;]/)
    .map((x) => x.trim())
    .filter(Boolean);

/** Configuração global dos providers. Secrets nunca voltam do backend. */
export function NotificationSettingsCard() {
  const toast = useToast();
  const { data } = useNotificationSettings();
  const save = useSaveNotificationSettings();
  const [form, setForm] = useState<NotificationSettingsInput>(EMPTY);
  const [defaultRecipients, setDefaultRecipients] = useState("");

  useEffect(() => {
    if (!data) return;
    setForm({
      email_enabled: data.email_enabled,
      smtp_host: data.smtp_host ?? "",
      smtp_port: data.smtp_port ?? 587,
      smtp_username: data.smtp_username ?? "",
      smtp_from: data.smtp_from ?? "",
      smtp_use_tls: data.smtp_use_tls,
      smtp_password: data.smtp_password_masked, // "********" quando definido
      bitrix_enabled: data.bitrix_enabled,
      bitrix_url: data.bitrix_url ?? "",
      bitrix_send_message_path: data.bitrix_send_message_path ?? "",
      bitrix_bot_id: data.bitrix_bot_id ?? "",
      bitrix_bot_token: data.bitrix_bot_token_masked,
      default_on_failure: data.default_on_failure,
      default_email_recipients: data.default_email_recipients,
      default_bitrix_dialog_id: data.default_bitrix_dialog_id ?? "",
    });
    setDefaultRecipients(data.default_email_recipients.join("\n"));
  }, [data]);

  const patch = (p: Partial<NotificationSettingsInput>) => setForm((f) => ({ ...f, ...p }));

  const submit = async () => {
    await save.mutateAsync({
      ...form,
      smtp_host: form.smtp_host || null,
      smtp_username: form.smtp_username || null,
      smtp_from: form.smtp_from || null,
      bitrix_url: form.bitrix_url || null,
      bitrix_send_message_path: form.bitrix_send_message_path || null,
      bitrix_bot_id: form.bitrix_bot_id || null,
      default_email_recipients: linesToList(defaultRecipients),
      default_bitrix_dialog_id: form.default_bitrix_dialog_id || null,
    });
    toast.success("Configuração de notificações salva");
  };

  return (
    <Card className="mt-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-faint">
          Notificações — configuração global
        </h2>
        <Button size="sm" loading={save.isPending} onClick={submit}>
          Salvar
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="space-y-3">
          <Switch
            checked={form.email_enabled}
            onChange={(v) => patch({ email_enabled: v })}
            label="E-mail (SMTP)"
          />
          <TextField
            label="SMTP Host"
            value={form.smtp_host ?? ""}
            onChange={(e) => patch({ smtp_host: e.target.value })}
          />
          <TextField
            label="SMTP Port"
            type="number"
            value={String(form.smtp_port ?? "")}
            onChange={(e) => patch({ smtp_port: Number(e.target.value) || null })}
          />
          <TextField
            label="Username"
            value={form.smtp_username ?? ""}
            onChange={(e) => patch({ smtp_username: e.target.value })}
          />
          <TextField
            label="Password"
            type="password"
            value={form.smtp_password ?? ""}
            placeholder={data?.smtp_password_masked ? SECRET_MASK : ""}
            onChange={(e) => patch({ smtp_password: e.target.value })}
            hint="Deixe ******** para manter a senha atual."
          />
          <TextField
            label="From"
            value={form.smtp_from ?? ""}
            placeholder="ci@empresa.com"
            onChange={(e) => patch({ smtp_from: e.target.value })}
          />
          <Switch
            checked={form.smtp_use_tls}
            onChange={(v) => patch({ smtp_use_tls: v })}
            label="Enable STARTTLS"
          />
        </section>

        <section className="space-y-3">
          <Switch
            checked={form.bitrix_enabled}
            onChange={(v) => patch({ bitrix_enabled: v })}
            label="Bitrix"
          />
          <TextField
            label="URL (base do portal)"
            value={form.bitrix_url ?? ""}
            placeholder="https://portal.bitrix24.com"
            onChange={(e) => patch({ bitrix_url: e.target.value })}
            hint="Só o host, sem /rest."
          />
          <TextField
            label="Send message path (recurso completo)"
            mono
            value={form.bitrix_send_message_path ?? ""}
            placeholder="/rest/1/xxxxxxxx/imbot.v2.Chat.Message.send"
            onChange={(e) => patch({ bitrix_send_message_path: e.target.value })}
            hint="Inclua o segmento do webhook. Com Bot ID+Token: imbot.v2.Chat.Message.send; sem: im.message.add."
          />
          <TextField
            label="Bot ID"
            value={form.bitrix_bot_id ?? ""}
            placeholder="93 (InvitaBot)"
            onChange={(e) => patch({ bitrix_bot_id: e.target.value })}
            hint="Padrão 93. NÃO é o chat/dialog — este vai por pipeline (ex.: chat3129)."
          />
          <TextField
            label="Bot Token"
            type="password"
            value={form.bitrix_bot_token ?? ""}
            placeholder={data?.bitrix_bot_token_masked ? SECRET_MASK : ""}
            onChange={(e) => patch({ bitrix_bot_token: e.target.value })}
            hint="Ou via env BITRIX_BOT_TOKEN. Nunca é exibido; deixe ******** para manter. Vazio = webhook de chat."
          />
        </section>
      </div>

      <div className="mt-5 rounded-lg border border-surface-border p-3">
        <Switch
          checked={form.default_on_failure}
          onChange={(v) => patch({ default_on_failure: v })}
          label="Notificar falha de qualquer pipeline (sem configuração própria)"
        />
        {form.default_on_failure && (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-fg-muted">
                Destinatários de e-mail padrão (um por linha)
              </span>
              <textarea
                rows={3}
                value={defaultRecipients}
                onChange={(e) => setDefaultRecipients(e.target.value)}
                placeholder={"oncall@empresa.com\ndevops@empresa.com"}
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 font-mono text-xs
                  focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </label>
            <TextField
              label="Dialog ID Bitrix padrão"
              mono
              value={form.default_bitrix_dialog_id ?? ""}
              placeholder="chat3129"
              onChange={(e) => patch({ default_bitrix_dialog_id: e.target.value })}
              hint="Usado quando o pipeline não define destino próprio."
            />
          </div>
        )}
      </div>

      <p className="mt-3 text-xs text-fg-faint">
        Também é possível definir tudo por variáveis de ambiente
        (<span className="font-mono">NOTIFY_SMTP_*</span>,{" "}
        <span className="font-mono">NOTIFY_BITRIX_*</span>,{" "}
        <span className="font-mono">NOTIFY_DEFAULT_*</span>) — o banco tem prioridade.
      </p>
    </Card>
  );
}
