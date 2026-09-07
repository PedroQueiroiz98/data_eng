import { useEffect, useState } from "react";
import {
  useSaveWorkflowNotifications,
  useWorkflowNotifications,
} from "@/hooks/useNotifications";
import type { NotificationConfigInput } from "@/lib/notifications";
import { Button, Dialog, Switch, TextField, useToast } from "@/ui";

interface Props {
  workflowId: string;
  workflowName?: string;
  open: boolean;
  onClose: () => void;
}

const linesToList = (s: string): string[] =>
  s
    .split(/[\n,;]/)
    .map((x) => x.trim())
    .filter(Boolean);

const EMPTY: NotificationConfigInput = {
  on_failure: true,
  on_success: false,
  on_retry: false,
  on_cancelled: false,
  on_started: false,
  email_enabled: false,
  email_recipients: [],
  email_cc: [],
  email_bcc: [],
  email_subject: null,
  bitrix_enabled: false,
  bitrix_dialog_id: null,
};

export function NotificationConfigDialog({ workflowId, workflowName, open, onClose }: Props) {
  const toast = useToast();
  const { data } = useWorkflowNotifications(workflowId, open);
  const save = useSaveWorkflowNotifications(workflowId);

  const [form, setForm] = useState<NotificationConfigInput>(EMPTY);
  const [recipients, setRecipients] = useState("");
  const [cc, setCc] = useState("");
  const [bcc, setBcc] = useState("");

  useEffect(() => {
    if (!data) return;
    setForm({
      on_failure: data.on_failure,
      on_success: data.on_success,
      on_retry: data.on_retry,
      on_cancelled: data.on_cancelled,
      on_started: data.on_started,
      email_enabled: data.email_enabled,
      email_recipients: data.email_recipients,
      email_cc: data.email_cc,
      email_bcc: data.email_bcc,
      email_subject: data.email_subject,
      bitrix_enabled: data.bitrix_enabled,
      bitrix_dialog_id: data.bitrix_dialog_id,
    });
    setRecipients(data.email_recipients.join("\n"));
    setCc(data.email_cc.join("\n"));
    setBcc(data.email_bcc.join("\n"));
  }, [data]);

  const patch = (p: Partial<NotificationConfigInput>) => setForm((f) => ({ ...f, ...p }));

  const submit = async () => {
    const body: NotificationConfigInput = {
      ...form,
      email_recipients: linesToList(recipients),
      email_cc: linesToList(cc),
      email_bcc: linesToList(bcc),
      email_subject: form.email_subject?.trim() || null,
      bitrix_dialog_id: form.bitrix_dialog_id?.trim() || null,
    };
    if (body.email_enabled && body.email_recipients.length === 0) {
      toast.error("Informe ao menos um destinatário de e-mail.");
      return;
    }
    if (body.bitrix_enabled && !body.bitrix_dialog_id) {
      toast.error("Informe o Dialog ID do Bitrix.");
      return;
    }
    await save.mutateAsync(body);
    toast.success("Notificações salvas");
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Notificações${workflowName ? ` · ${workflowName}` : ""}`}
      width="lg"
      footer={
        <>
          <Button variant="text" onClick={onClose}>
            Cancelar
          </Button>
          <Button loading={save.isPending} onClick={submit}>
            Salvar
          </Button>
        </>
      }
    >
      <div className="space-y-5 text-sm">
        <section className="space-y-2">
          <Switch
            checked={form.on_failure}
            onChange={(v) => patch({ on_failure: v })}
            label="Notificar quando o pipeline falhar"
          />
          <p className="text-xs text-fg-faint">
            OnSuccess / OnRetry / OnCancelled serão habilitados numa próxima versão.
          </p>
        </section>

        <section className="rounded-lg border border-surface-border p-3">
          <Switch
            checked={form.email_enabled}
            onChange={(v) => patch({ email_enabled: v })}
            label="Canal: E-mail"
          />
          {form.email_enabled && (
            <div className="mt-3 space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-fg-muted">
                  Destinatários (um por linha)
                </span>
                <textarea
                  rows={3}
                  value={recipients}
                  onChange={(e) => setRecipients(e.target.value)}
                  placeholder={"pedro@empresa.com\nsuporte@empresa.com"}
                  className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 font-mono text-xs
                    focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-fg-muted">CC</span>
                  <textarea
                    rows={2}
                    value={cc}
                    onChange={(e) => setCc(e.target.value)}
                    className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 font-mono text-xs
                      focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-fg-muted">BCC</span>
                  <textarea
                    rows={2}
                    value={bcc}
                    onChange={(e) => setBcc(e.target.value)}
                    className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 font-mono text-xs
                      focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </label>
              </div>
              <TextField
                label="Assunto (opcional)"
                value={form.email_subject ?? ""}
                placeholder="[JOB FAILED] {pipeline} - {job}"
                onChange={(e) => patch({ email_subject: e.target.value })}
              />
            </div>
          )}
        </section>

        <section className="rounded-lg border border-surface-border p-3">
          <Switch
            checked={form.bitrix_enabled}
            onChange={(v) => patch({ bitrix_enabled: v })}
            label="Canal: Bitrix"
          />
          {form.bitrix_enabled && (
            <div className="mt-3">
              <TextField
                label="Dialog ID (destino)"
                mono
                value={form.bitrix_dialog_id ?? ""}
                placeholder="chat3129"
                onChange={(e) => patch({ bitrix_dialog_id: e.target.value })}
                hint="chat<N> para um grupo, ou o ID numérico do usuário para conversa direta."
              />
              <p className="mt-1 text-xs text-fg-faint">
                URL, bot e token do Bitrix ficam na configuração global (backend). Aqui só o destino.
              </p>
            </div>
          )}
        </section>
      </div>
    </Dialog>
  );
}
