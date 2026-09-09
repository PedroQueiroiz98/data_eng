import { useEffect, useRef, useState } from "react";
import { useAssistantStore } from "@/store/assistant";
import { dispatchAiCommand } from "@/components/assistant/AiCellMenu";
import { SendIcon } from "@/ui/icons";

interface Props {
  cellId: string;
}

/** Prompt "Ask AI" (Ctrl+K) ancorado numa célula. */
export function AiInlineWidget({ cellId }: Props) {
  const open = useAssistantStore((s) => s.askCellId === cellId);
  const close = useAssistantStore((s) => s.openAsk);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setValue("");
      inputRef.current?.focus();
    }
  }, [open]);

  if (!open) return null;

  const submit = () => {
    const q = value.trim();
    if (!q) return;
    dispatchAiCommand("GENERATE", cellId, undefined, q);
    close(null);
  };

  return (
    <div className="border-b border-primary/30 bg-primary-container/10 px-2 py-1.5">
      <div className="flex items-center gap-2">
        <span className="text-xs text-primary">✨</span>
        <input
          ref={inputRef}
          value={value}
          placeholder="Descreva o que gerar… (Enter para enviar, Esc para fechar)"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-fg-faint"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submit();
            } else if (e.key === "Escape") {
              e.preventDefault();
              close(null);
            }
          }}
        />
        <button
          type="button"
          className="rounded p-1 text-primary hover:bg-surface-variant"
          onClick={submit}
          title="Enviar"
        >
          <SendIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
