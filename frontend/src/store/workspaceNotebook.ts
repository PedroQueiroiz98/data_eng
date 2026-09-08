/**
 * Estado local (por aba) de um notebook do Workspace. Independente do store
 * singleton `useNotebookEditor` (usado por `/notebooks/:id`) para permitir N
 * notebooks abertos ao mesmo tempo.
 */

import type { CellOutput, NotebookCell, NotebookContent } from "@/lib/notebooks";

export type RunStatus = "idle" | "running" | "ok" | "error" | "cancelled";

export interface WCell {
  id: string;
  cell_type: "code" | "markdown" | "raw";
  source: string;
  metadata: Record<string, unknown>;
  outputs: CellOutput[];
  execution_count: number | null;
  runStatus: RunStatus;
  durationMs?: number;
}

export interface WNotebookState {
  cells: WCell[];
  metadata: Record<string, unknown>;
  nbformat: number;
  nbformatMinor: number;
  loaded: boolean;
}

export const emptyState: WNotebookState = {
  cells: [],
  metadata: {},
  nbformat: 4,
  nbformatMinor: 5,
  loaded: false,
};

const uid = (): string =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `c-${Math.random().toString(36).slice(2)}`;

const asString = (s: string | string[]): string =>
  Array.isArray(s) ? s.join("") : s;

const toWCell = (c: NotebookCell): WCell => ({
  id: uid(),
  cell_type: c.cell_type,
  source: asString(c.source),
  metadata: (c.metadata ?? {}) as Record<string, unknown>,
  outputs: c.outputs ?? [],
  execution_count: c.execution_count ?? null,
  runStatus: "idle",
});

const blank = (type: WCell["cell_type"]): WCell => ({
  id: uid(),
  cell_type: type,
  source: "",
  metadata: {},
  outputs: [],
  execution_count: null,
  runStatus: "idle",
});

export type WAction =
  | { type: "load"; content: NotebookContent }
  | { type: "setSource"; id: string; source: string }
  | { type: "setType"; id: string; cellType: WCell["cell_type"] }
  | { type: "add"; afterId: string | null; cellType: WCell["cell_type"] }
  | { type: "remove"; id: string }
  | { type: "move"; id: string; dir: "up" | "down" }
  | { type: "duplicate"; id: string }
  | { type: "clearOutputs" }
  | { type: "runStart"; id: string }
  | { type: "cellOutput"; id: string; output: CellOutput }
  | {
      type: "runFinish";
      id: string;
      status: RunStatus;
      execution_count: number | null;
      durationMs?: number;
      outputs?: CellOutput[];
    };

const idx = (cells: WCell[], id: string): number => cells.findIndex((c) => c.id === id);

export function reducer(state: WNotebookState, action: WAction): WNotebookState {
  switch (action.type) {
    case "load": {
      const c = action.content;
      return {
        cells: (c.cells ?? []).map(toWCell),
        metadata: c.metadata ?? {},
        nbformat: c.nbformat ?? 4,
        nbformatMinor: c.nbformat_minor ?? 5,
        loaded: true,
      };
    }
    case "setSource":
      return {
        ...state,
        cells: state.cells.map((c) =>
          c.id === action.id ? { ...c, source: action.source } : c,
        ),
      };
    case "setType":
      return {
        ...state,
        cells: state.cells.map((c) =>
          c.id === action.id
            ? {
                ...c,
                cell_type: action.cellType,
                outputs: action.cellType === "code" ? c.outputs : [],
              }
            : c,
        ),
      };
    case "add": {
      const cell = blank(action.cellType);
      const at = action.afterId ? idx(state.cells, action.afterId) + 1 : state.cells.length;
      return {
        ...state,
        cells: [...state.cells.slice(0, at), cell, ...state.cells.slice(at)],
      };
    }
    case "remove":
      return { ...state, cells: state.cells.filter((c) => c.id !== action.id) };
    case "move": {
      const at = idx(state.cells, action.id);
      const to = action.dir === "up" ? at - 1 : at + 1;
      if (at < 0 || to < 0 || to >= state.cells.length) return state;
      const cells = [...state.cells];
      const [m] = cells.splice(at, 1);
      cells.splice(to, 0, m!);
      return { ...state, cells };
    }
    case "duplicate": {
      const at = idx(state.cells, action.id);
      if (at < 0) return state;
      const src = state.cells[at]!;
      const copy: WCell = { ...src, id: uid(), outputs: [], runStatus: "idle" };
      return {
        ...state,
        cells: [...state.cells.slice(0, at + 1), copy, ...state.cells.slice(at + 1)],
      };
    }
    case "clearOutputs":
      return {
        ...state,
        cells: state.cells.map((c) => ({
          ...c,
          outputs: [],
          execution_count: null,
          runStatus: "idle",
          durationMs: undefined,
        })),
      };
    case "runStart":
      return {
        ...state,
        cells: state.cells.map((c) =>
          c.id === action.id ? { ...c, outputs: [], runStatus: "running" } : c,
        ),
      };
    case "cellOutput":
      return {
        ...state,
        cells: state.cells.map((c) =>
          c.id === action.id ? { ...c, outputs: [...c.outputs, action.output] } : c,
        ),
      };
    case "runFinish":
      return {
        ...state,
        cells: state.cells.map((c) =>
          c.id === action.id
            ? {
                ...c,
                runStatus: action.status,
                execution_count: action.execution_count,
                durationMs: action.durationMs,
                outputs: action.outputs ?? c.outputs,
              }
            : c,
        ),
      };
    default:
      return state;
  }
}

export function toContent(state: WNotebookState): NotebookContent {
  return {
    nbformat: state.nbformat,
    nbformat_minor: state.nbformatMinor,
    metadata: state.metadata,
    cells: state.cells.map((c) => {
      const base: NotebookCell = {
        cell_type: c.cell_type,
        source: c.source,
        metadata: (c.metadata ?? {}) as NotebookCell["metadata"],
      };
      if (c.cell_type === "code") {
        base.outputs = c.outputs;
        base.execution_count = c.execution_count;
      }
      return base;
    }),
  };
}
