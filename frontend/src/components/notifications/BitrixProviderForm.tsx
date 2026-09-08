import { useState } from "react";
import { IconButton, TextField } from "@/ui";
import { ViewIcon } from "@/ui/icons";
import { SECRET_MASK, type BitrixConfig } from "@/lib/notificationProviders";

export interface BitrixFormState {
  url: string;
  send_message_path: string;
  bot_id: string;
  dialog_id: string;
  token: string;
}

export const EMPTY_BITRIX: BitrixFormState = {
  url: "",
  send_message_path: "",
  bot_id: "",
  dialog_id: "",
  token: "",
};

export function bitrixStateFromConfig(
  cfg: Record<string, unknown>,
  hasCredential: boolean,
): BitrixFormState {
  const c = cfg as Partial<BitrixConfig>;
  return {
    url: c.url ?? "",
    send_message_path: c.send_message_path ?? "",
    bot_id: c.bot_id ?? "",
    dialog_id: c.dialog_id ?? "",
    token: hasCredential ? SECRET_MASK : "",
  };
}

export function bitrixConfigFromState(s: BitrixFormState): {
  configuration: Record<string, unknown>;
  secret: string | null;
} {
  return {
    configuration: {
      url: s.url.trim(),
      send_message_path: s.send_message_path.trim() || null,
      bot_id: s.bot_id.trim() || null,
      dialog_id: s.dialog_id.trim(),
    },
    secret: s.token,
  };
}

interface Props {
  value: BitrixFormState;
  onChange: (patch: Partial<BitrixFormState>) => void;
}

export function BitrixProviderForm({ value, onChange }: Props) {
  const [reveal, setReveal] = useState(false);
  return (
    <div className="space-y-3">
      <TextField
        label="URL do Bitrix *"
        value={value.url}
        placeholder="https://empresa.bitrix24.com.br"
        onChange={(e) => onChange({ url: e.target.value })}
        hint="URL da sua instância Bitrix."
      />
      <TextField
        label="Send message path"
        mono
        value={value.send_message_path}
        placeholder="/rest/1/xxxx/imbot.v2.Chat.Message.send"
        onChange={(e) => onChange({ send_message_path: e.target.value })}
        hint="Opcional. Inclua o segmento do webhook quando aplicável."
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label="Bot ID"
          value={value.bot_id}
          placeholder="93"
          onChange={(e) => onChange({ bot_id: e.target.value })}
          hint="Vazio = webhook de chat."
        />
        <TextField
          label="Dialog ID *"
          mono
          value={value.dialog_id}
          placeholder="chat3129"
          onChange={(e) => onChange({ dialog_id: e.target.value })}
        />
      </div>
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <TextField
            label="Token / Credential *"
            type={reveal ? "text" : "password"}
            value={value.token}
            placeholder={value.token === SECRET_MASK ? SECRET_MASK : ""}
            onChange={(e) => onChange({ token: e.target.value })}
            hint="Nunca é exibido depois de salvo. Deixe ******** para manter."
          />
        </div>
        <IconButton
          label={reveal ? "Ocultar" : "Mostrar"}
          size="sm"
          icon={<ViewIcon className="h-4 w-4" />}
          onClick={() => setReveal((v) => !v)}
          className="mb-5"
        />
      </div>
    </div>
  );
}
