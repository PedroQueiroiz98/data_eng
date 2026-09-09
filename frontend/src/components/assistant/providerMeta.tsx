import type { ComponentType } from "react";
import { ChatIcon } from "@/ui/icons";
import type { AssistantProviderType } from "@/lib/assistantProviders";

export const AI_PROVIDER_META: Record<
  AssistantProviderType,
  { label: string; Icon: ComponentType<{ className?: string }>; hint: string }
> = {
  OPENAI: { label: "OpenAI", Icon: ChatIcon, hint: "api.openai.com / compatível" },
  AZURE_OPENAI: { label: "Azure OpenAI", Icon: ChatIcon, hint: "endpoint + deployment do Azure" },
  OLLAMA: { label: "Ollama", Icon: ChatIcon, hint: "modelos locais (localhost:11434)" },
};

export const AI_TASK_LABEL: Record<string, string> = {
  GENERATE: "Gerar código",
  EXPLAIN: "Explicar",
  FIX: "Corrigir",
  OPTIMIZE: "Otimizar",
  TESTS: "Gerar testes",
  CONTINUE: "Continuar",
  CONVERT: "Converter",
  DOCSTRING: "Documentar",
  CHAT: "Chat",
  INLINE: "Inline",
};
