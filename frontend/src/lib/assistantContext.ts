/**
 * O editor de notebook publica aqui um "provedor de contexto" para a IA
 * (células atuais, path, sessão de kernel, erro recente). Mesma ideia do
 * `setLspDoc` — evita prop-drilling entre o editor e o painel de chat / Ctrl+K.
 */
import type { AiContextIn } from "@/lib/assistant";

export interface NotebookAiContext {
  /** contexto para uma tarefa ancorada numa célula (por id) */
  forCell: (cellId: string, opts?: { selection?: string }) => AiContextIn | null;
  /** contexto geral do notebook (chat) */
  overview: () => AiContextIn | null;
}

let provider: NotebookAiContext | null = null;

export function setNotebookAiContext(p: NotebookAiContext | null): void {
  provider = p;
}

export function notebookAiContext(): NotebookAiContext | null {
  return provider;
}
