import { Switch, TextArea, TextField } from "@/ui";
import { SECRET_MASK, type EmailConfig } from "@/lib/notificationProviders";
import { linesToList } from "@/components/notifications/providerMeta";

export interface EmailFormState {
  host: string;
  port: string;
  username: string;
  from_email: string;
  from_name: string;
  use_tls: boolean;
  recipients: string;
  cc: string;
  bcc: string;
  password: string;
}

export const EMPTY_EMAIL: EmailFormState = {
  host: "",
  port: "587",
  username: "",
  from_email: "",
  from_name: "",
  use_tls: true,
  recipients: "",
  cc: "",
  bcc: "",
  password: "",
};

export function emailStateFromConfig(
  cfg: Record<string, unknown>,
  hasPassword: boolean,
): EmailFormState {
  const c = cfg as Partial<EmailConfig>;
  return {
    host: c.host ?? "",
    port: c.port != null ? String(c.port) : "587",
    username: c.username ?? "",
    from_email: c.from_email ?? "",
    from_name: c.from_name ?? "",
    use_tls: c.use_tls ?? true,
    recipients: (c.recipients ?? []).join("\n"),
    cc: (c.cc ?? []).join("\n"),
    bcc: (c.bcc ?? []).join("\n"),
    password: hasPassword ? SECRET_MASK : "",
  };
}

export function emailConfigFromState(s: EmailFormState): {
  configuration: Record<string, unknown>;
  secret: string | null;
} {
  return {
    configuration: {
      host: s.host.trim(),
      port: Number(s.port) || null,
      username: s.username.trim() || null,
      from_email: s.from_email.trim(),
      from_name: s.from_name.trim() || null,
      use_tls: s.use_tls,
      recipients: linesToList(s.recipients),
      cc: linesToList(s.cc),
      bcc: linesToList(s.bcc),
    },
    secret: s.password,
  };
}

interface Props {
  value: EmailFormState;
  onChange: (patch: Partial<EmailFormState>) => void;
}

export function EmailProviderForm({ value, onChange }: Props) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label="SMTP Host *"
          value={value.host}
          placeholder="smtp.empresa.com"
          onChange={(e) => onChange({ host: e.target.value })}
        />
        <TextField
          label="SMTP Port *"
          type="number"
          value={value.port}
          onChange={(e) => onChange({ port: e.target.value })}
        />
      </div>
      <Switch
        checked={value.use_tls}
        onChange={(v) => onChange({ use_tls: v })}
        label="Usar TLS (STARTTLS)"
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label="Username"
          value={value.username}
          onChange={(e) => onChange({ username: e.target.value })}
        />
        <TextField
          label="Password *"
          type="password"
          value={value.password}
          placeholder={value.password === SECRET_MASK ? SECRET_MASK : ""}
          onChange={(e) => onChange({ password: e.target.value })}
          hint="Deixe ******** para manter a senha atual."
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label="From Email *"
          value={value.from_email}
          placeholder="noreply@empresa.com"
          onChange={(e) => onChange({ from_email: e.target.value })}
        />
        <TextField
          label="From Name *"
          value={value.from_name}
          placeholder="Data Platform"
          onChange={(e) => onChange({ from_name: e.target.value })}
        />
      </div>
      <TextArea
        label="Destinatários * (um por linha)"
        rows={3}
        value={value.recipients}
        placeholder={"data-team@empresa.com\nsuporte@empresa.com"}
        onChange={(e) => onChange({ recipients: e.target.value })}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <TextArea
          label="CC"
          rows={2}
          value={value.cc}
          onChange={(e) => onChange({ cc: e.target.value })}
        />
        <TextArea
          label="BCC"
          rows={2}
          value={value.bcc}
          onChange={(e) => onChange({ bcc: e.target.value })}
        />
      </div>
    </div>
  );
}
