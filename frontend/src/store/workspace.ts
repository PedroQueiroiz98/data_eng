import { create } from "zustand";

export type RightPanelTab = "output" | "git" | "history";

interface WorkspaceState {
  activeWorkspaceId: string | null;
  openPath: string | null;
  expandedDirs: Set<string>;
  dirtyByPath: Record<string, boolean>;
  rightPanelTab: RightPanelTab;

  setActiveWorkspace: (id: string | null) => void;
  openFile: (path: string) => void;
  toggleDir: (path: string) => void;
  setExpanded: (path: string, expanded: boolean) => void;
  markDirty: (path: string, dirty: boolean) => void;
  setRightPanelTab: (tab: RightPanelTab) => void;
  reset: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  activeWorkspaceId: null,
  openPath: null,
  expandedDirs: new Set<string>(),
  dirtyByPath: {},
  rightPanelTab: "output",

  setActiveWorkspace: (id) =>
    set((s) =>
      s.activeWorkspaceId === id
        ? {}
        : {
            activeWorkspaceId: id,
            openPath: null,
            expandedDirs: new Set(),
            dirtyByPath: {},
          },
    ),
  openFile: (path) => set({ openPath: path }),
  toggleDir: (path) =>
    set((s) => {
      const next = new Set(s.expandedDirs);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return { expandedDirs: next };
    }),
  setExpanded: (path, expanded) =>
    set((s) => {
      const next = new Set(s.expandedDirs);
      if (expanded) next.add(path);
      else next.delete(path);
      return { expandedDirs: next };
    }),
  markDirty: (path, dirty) =>
    set((s) => ({ dirtyByPath: { ...s.dirtyByPath, [path]: dirty } })),
  setRightPanelTab: (tab) => set({ rightPanelTab: tab }),
  reset: () =>
    set({
      openPath: null,
      expandedDirs: new Set(),
      dirtyByPath: {},
      rightPanelTab: "output",
    }),
}));
