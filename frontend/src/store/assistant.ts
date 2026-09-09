import { create } from "zustand";
import type { AiErrorIn, AssistantTask } from "@/lib/assistant";

export interface AiCellResult {
  task: AssistantTask;
  text: string;
  streaming: boolean;
  error: string | null;
  /** código-fonte da célula no momento do pedido (para o diff) */
  originalSource: string;
}

interface AssistantUIState {
  available: boolean;
  inlineEnabled: boolean;
  providerType: string | null;
  /** Ctrl+K aberto para esta célula */
  askCellId: string | null;
  /** resultado de IA ancorado por célula */
  resultByCell: Record<string, AiCellResult>;
  /** último erro de execução por célula (para "Corrigir com IA") */
  lastErrorByCell: Record<string, AiErrorIn>;

  setAvailability: (a: {
    configured: boolean;
    inline_enabled: boolean;
    provider_type: string | null;
  }) => void;
  openAsk: (cellId: string | null) => void;
  setResult: (cellId: string, r: AiCellResult | null) => void;
  appendDelta: (cellId: string, delta: string) => void;
  finishResult: (cellId: string, error: string | null) => void;
  setCellError: (cellId: string, err: AiErrorIn | null) => void;
}

export const useAssistantStore = create<AssistantUIState>((set) => ({
  available: false,
  inlineEnabled: false,
  providerType: null,
  askCellId: null,
  resultByCell: {},
  lastErrorByCell: {},

  setAvailability: (a) =>
    set({
      available: a.configured,
      inlineEnabled: a.configured && a.inline_enabled,
      providerType: a.provider_type,
    }),

  openAsk: (cellId) => set({ askCellId: cellId }),

  setResult: (cellId, r) =>
    set((s) => {
      const next = { ...s.resultByCell };
      if (r) next[cellId] = r;
      else delete next[cellId];
      return { resultByCell: next };
    }),

  appendDelta: (cellId, delta) =>
    set((s) => {
      const cur = s.resultByCell[cellId];
      if (!cur) return {};
      return {
        resultByCell: { ...s.resultByCell, [cellId]: { ...cur, text: cur.text + delta } },
      };
    }),

  finishResult: (cellId, error) =>
    set((s) => {
      const cur = s.resultByCell[cellId];
      if (!cur) return {};
      return {
        resultByCell: {
          ...s.resultByCell,
          [cellId]: { ...cur, streaming: false, error },
        },
      };
    }),

  setCellError: (cellId, err) =>
    set((s) => {
      const next = { ...s.lastErrorByCell };
      if (err) next[cellId] = err;
      else delete next[cellId];
      return { lastErrorByCell: next };
    }),
}));

/** Snapshot fora de componentes React (usado pelos providers do Monaco). */
export const getAssistantState = (): AssistantUIState => useAssistantStore.getState();
