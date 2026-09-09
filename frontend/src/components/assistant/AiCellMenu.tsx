import { useEffect, useRef, useState } from "react";
import type { AssistantTask } from "@/lib/assistant";
import { getAssistantState, useAssistantStore } from "@/store/assistant";
import { useEditorConfig } from "@/lib/editorConfig";

interface Props {
  cellId: string;
}

const ITEMS: { task: AssistantTask; label: string; lang?: string }[] = [
  { task: "GENERATE", label: "Gerar código…" },
  { task: "EXPLAIN", label: "Explicar" },
  { task: "FIX", label: "Corrigir" },
  { task: "OPTIMIZE", label: "Otimizar" },
  { task: "DOCSTRING", label: "Adicionar documentação" },
  { task: "TESTS", label: "Gerar testes" },
  { task: "CONTINUE", label: "Continuar" },
  { task: "CONVERT", label: "Converter para SQL", lang: "SQL" },
];

export interface AiCommandDetail {
  task: AssistantTask;
  cellId: string;
  targetLanguage?: string;
  instruction?: string;
}

export function dispatchAiCommand(
  task: AssistantTask,
  cellId: string,
  targetLanguage?: string,
  instruction?: string,
) {
  window.dispatchEvent(
    new CustomEvent<AiCommandDetail>("nbp:ai-command", {
      detail: { task, cellId, targetLanguage, instruction },
    }),
  );
}

export function AiCellMenu({ cellId }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const aiEnabled = useEditorConfig((s) => s.config.ai.enabled);
  const available = useAssistantStore((s) => s.available);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!aiEnabled || !available) return null;

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        className="rounded px-1.5 py-0.5 text-xs text-primary hover:bg-surface-variant"
        title="Assistente de IA (Ctrl+K)"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        ✨ AI
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-40 mt-1 min-w-48 overflow-hidden rounded-md
            border border-surface-border bg-surface py-1 text-sm shadow-e3"
        >
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-1.5 text-left hover:bg-surface-variant"
            onClick={() => {
              setOpen(false);
              getAssistantState().openAsk(cellId);
            }}
          >
            ✨ Perguntar à IA… (Ctrl+K)
          </button>
          <div className="my-1 h-px bg-surface-border" />
          {ITEMS.map((it) => (
            <button
              key={it.task + (it.lang ?? "")}
              type="button"
              role="menuitem"
              className="block w-full px-3 py-1.5 text-left hover:bg-surface-variant"
              onClick={() => {
                setOpen(false);
                dispatchAiCommand(it.task, cellId, it.lang);
              }}
            >
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
