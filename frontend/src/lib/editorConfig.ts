/**
 * Configuração do editor inteligente. Client-side, persistida em localStorage,
 * extensível. (Config server-side chega junto com a camada de IA.)
 */
import { create } from "zustand";

export interface EditorConfig {
  editor: {
    autocomplete: boolean;
    diagnostics: boolean;
    signatureHelp: boolean;
    hover: boolean;
    inlineSuggestions: boolean;
  };
  python: {
    languageServer: "jedi" | "pyright";
  };
  ai: {
    enabled: boolean;
  };
}

export const DEFAULT_CONFIG: EditorConfig = {
  editor: {
    autocomplete: true,
    diagnostics: true,
    signatureHelp: true,
    hover: true,
    inlineSuggestions: false,
  },
  python: { languageServer: "jedi" },
  ai: { enabled: false },
};

const KEY = "nbp.editor.config";

function deepMerge<T>(base: T, override: unknown): T {
  if (override == null || typeof override !== "object") return base;
  const out = { ...base } as Record<string, unknown>;
  for (const [k, v] of Object.entries(override as Record<string, unknown>)) {
    const cur = out[k];
    if (cur && typeof cur === "object" && !Array.isArray(cur) && v && typeof v === "object") {
      out[k] = deepMerge(cur, v);
    } else if (v !== undefined) {
      out[k] = v;
    }
  }
  return out as T;
}

function load(): EditorConfig {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return deepMerge(DEFAULT_CONFIG, JSON.parse(raw));
  } catch {
    /* ignore */
  }
  return DEFAULT_CONFIG;
}

function persist(cfg: EditorConfig): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(cfg));
  } catch {
    /* ignore */
  }
}

interface ConfigStore {
  config: EditorConfig;
  setSection: <K extends keyof EditorConfig>(section: K, patch: Partial<EditorConfig[K]>) => void;
  reset: () => void;
}

export const useEditorConfig = create<ConfigStore>((set, get) => ({
  config: load(),
  setSection: (section, patch) => {
    const next = {
      ...get().config,
      [section]: { ...get().config[section], ...patch },
    };
    persist(next);
    set({ config: next });
  },
  reset: () => {
    persist(DEFAULT_CONFIG);
    set({ config: DEFAULT_CONFIG });
  },
}));

/** Snapshot fora de componentes React (usado pelos providers do Monaco). */
export const getEditorConfig = (): EditorConfig => useEditorConfig.getState().config;
