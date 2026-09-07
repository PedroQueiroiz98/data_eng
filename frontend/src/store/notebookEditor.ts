import { create } from "zustand";
import type { CellType, NotebookCell, NotebookContent } from "@/lib/notebooks";

export interface EditorCell extends NotebookCell {
  /** id local estável para keys de lista e seleção */
  localId: string;
}

interface EditorState {
  cells: EditorCell[];
  baseMetadata: Record<string, unknown>;
  /** requisitos pip (um por linha) — persistidos em metadata.nbplatform.dependencies */
  dependencies: string;
  nbformat: number;
  nbformatMinor: number;
  selectedId: string | null;
  dirty: boolean;

  load: (content: NotebookContent) => void;
  select: (localId: string | null) => void;
  setDependencies: (text: string) => void;
  setSource: (localId: string, source: string) => void;
  setCellType: (localId: string, type: CellType) => void;
  addCell: (type: CellType, afterLocalId: string | null) => void;
  removeCell: (localId: string) => void;
  duplicateCell: (localId: string) => void;
  moveCell: (localId: string, direction: "up" | "down") => void;
  toContent: () => NotebookContent;
  markSaved: () => void;
}

const newLocalId = (): string =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `c-${Math.random().toString(36).slice(2)}`;

const blankCell = (type: CellType): EditorCell => ({
  localId: newLocalId(),
  cell_type: type,
  source: "",
  metadata: {},
  ...(type === "code" ? { outputs: [], execution_count: null } : {}),
});

const toEditorCell = (cell: NotebookCell): EditorCell => ({
  ...cell,
  source: Array.isArray(cell.source) ? cell.source.join("") : cell.source,
  metadata: cell.metadata ?? {},
  localId: newLocalId(),
});

const indexOf = (cells: EditorCell[], localId: string): number =>
  cells.findIndex((c) => c.localId === localId);

const NBP_META_KEY = "nbplatform";

const readDependencies = (metadata: Record<string, unknown> | undefined): string => {
  const section = metadata?.[NBP_META_KEY];
  const raw =
    section && typeof section === "object"
      ? (section as Record<string, unknown>).dependencies
      : undefined;
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) return raw.filter((x): x is string => typeof x === "string").join("\n");
  return "";
};

const parseDependencies = (text: string): string[] =>
  text
    .split("\n")
    .map((line) => line.split("#", 1)[0]!.trim())
    .filter(Boolean);

export const useNotebookEditor = create<EditorState>((set, get) => ({
  cells: [],
  baseMetadata: {},
  dependencies: "",
  nbformat: 4,
  nbformatMinor: 5,
  selectedId: null,
  dirty: false,

  load: (content) =>
    set({
      cells: content.cells.map(toEditorCell),
      baseMetadata: content.metadata ?? {},
      dependencies: readDependencies(content.metadata),
      nbformat: content.nbformat ?? 4,
      nbformatMinor: content.nbformat_minor ?? 5,
      selectedId: content.cells.length ? null : null,
      dirty: false,
    }),

  select: (localId) => set({ selectedId: localId }),

  setDependencies: (text) => set({ dependencies: text, dirty: true }),

  setSource: (localId, source) =>
    set((s) => ({
      dirty: true,
      cells: s.cells.map((c) => (c.localId === localId ? { ...c, source } : c)),
    })),

  setCellType: (localId, type) =>
    set((s) => ({
      dirty: true,
      cells: s.cells.map((c) =>
        c.localId === localId
          ? {
              ...c,
              cell_type: type,
              ...(type === "code"
                ? { outputs: c.outputs ?? [], execution_count: c.execution_count ?? null }
                : { outputs: undefined, execution_count: undefined }),
            }
          : c,
      ),
    })),

  addCell: (type, afterLocalId) =>
    set((s) => {
      const cell = blankCell(type);
      const at = afterLocalId ? indexOf(s.cells, afterLocalId) + 1 : s.cells.length;
      const cells = [...s.cells.slice(0, at), cell, ...s.cells.slice(at)];
      return { cells, selectedId: cell.localId, dirty: true };
    }),

  removeCell: (localId) =>
    set((s) => ({
      dirty: true,
      cells: s.cells.filter((c) => c.localId !== localId),
      selectedId: s.selectedId === localId ? null : s.selectedId,
    })),

  duplicateCell: (localId) =>
    set((s) => {
      const at = indexOf(s.cells, localId);
      if (at < 0) return s;
      const src = s.cells[at]!;
      const copy: EditorCell = { ...src, localId: newLocalId(), outputs: src.outputs ? [] : undefined };
      const cells = [...s.cells.slice(0, at + 1), copy, ...s.cells.slice(at + 1)];
      return { cells, selectedId: copy.localId, dirty: true };
    }),

  moveCell: (localId, direction) =>
    set((s) => {
      const at = indexOf(s.cells, localId);
      const to = direction === "up" ? at - 1 : at + 1;
      if (at < 0 || to < 0 || to >= s.cells.length) return s;
      const cells = [...s.cells];
      const [moved] = cells.splice(at, 1);
      cells.splice(to, 0, moved!);
      return { cells, dirty: true };
    }),

  toContent: () => {
    const s = get();
    const deps = parseDependencies(s.dependencies);
    const prevSection =
      s.baseMetadata[NBP_META_KEY] && typeof s.baseMetadata[NBP_META_KEY] === "object"
        ? (s.baseMetadata[NBP_META_KEY] as Record<string, unknown>)
        : undefined;
    const metadata: Record<string, unknown> = { ...s.baseMetadata };
    if (deps.length > 0) {
      metadata[NBP_META_KEY] = { ...prevSection, dependencies: deps };
    } else if (prevSection) {
      const rest: Record<string, unknown> = {};
      for (const [k, val] of Object.entries(prevSection)) {
        if (k !== "dependencies") rest[k] = val;
      }
      if (Object.keys(rest).length > 0) metadata[NBP_META_KEY] = rest;
      else delete metadata[NBP_META_KEY];
    }
    return {
      nbformat: s.nbformat,
      nbformat_minor: s.nbformatMinor,
      metadata,
      cells: s.cells.map((c) => {
        const base: Record<string, unknown> = {
          cell_type: c.cell_type,
          source: c.source,
          metadata: c.metadata ?? {},
        };
        if (c.id) base.id = c.id;
        if (c.cell_type === "code") {
          base.outputs = c.outputs ?? [];
          base.execution_count = c.execution_count ?? null;
        }
        return base as unknown as NotebookCell;
      }),
    };
  },

  markSaved: () => set({ dirty: false }),
}));
