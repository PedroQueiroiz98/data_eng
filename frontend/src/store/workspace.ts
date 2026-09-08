import { create } from "zustand";
import { persist } from "zustand/middleware";
import { baseName, kindFromPath, type TabKind } from "@/lib/workspaceFiles";

export type { TabKind };
export type RightPanelTab = "output" | "git" | "history";

export interface WorkspaceTab {
  path: string;
  kind: TabKind;
  title: string;
}

/** Estado de UI persistido por workspace. */
export interface WorkspaceView {
  tabs: WorkspaceTab[];
  activeTab: string | null;
  expandedDirs: string[];
  explorerWidth: number;
  explorerCollapsed: boolean;
  panelHeight: number;
  panelCollapsed: boolean;
  panelTab: "execution" | "output" | "problems" | "git";
}

export interface AutosaveConfig {
  enabled: boolean;
  intervalMs: number;
}

const DEFAULT_VIEW: WorkspaceView = Object.freeze({
  tabs: [],
  activeTab: null,
  expandedDirs: [],
  explorerWidth: 260,
  explorerCollapsed: false,
  panelHeight: 220,
  panelCollapsed: true,
  panelTab: "execution",
}) as WorkspaceView;

const EXPLORER_MIN = 160;
const EXPLORER_MAX = 560;
const PANEL_MIN = 120;
const PANEL_MAX = 640;

interface WorkspaceState {
  activeWorkspaceId: string | null;
  byWorkspace: Record<string, WorkspaceView>;
  /** transiente — não persistido */
  dirtyByPath: Record<string, boolean>;
  /** transiente — pilha de abas fechadas p/ "Reopen Closed" */
  recentlyClosed: WorkspaceTab[];
  autosave: AutosaveConfig;
  rightPanelTab: RightPanelTab;

  setActiveWorkspace: (id: string | null) => void;
  view: () => WorkspaceView;

  openTab: (path: string, kind?: TabKind) => void;
  closeTab: (path: string) => void;
  closeOthers: (path: string) => void;
  closeToRight: (path: string) => void;
  closeAll: () => void;
  reopenClosed: () => void;
  reorderTabs: (from: number, to: number) => void;
  setActiveTab: (path: string) => void;
  renameTabPath: (from: string, to: string) => void;

  toggleDir: (path: string) => void;
  setExpanded: (path: string, expanded: boolean) => void;
  collapseAllDirs: () => void;

  markDirty: (path: string, dirty: boolean) => void;
  clearDirty: (path: string) => void;

  setExplorerWidth: (px: number) => void;
  toggleExplorer: (open?: boolean) => void;
  setPanelHeight: (px: number) => void;
  togglePanel: (open?: boolean) => void;
  setPanelTab: (tab: WorkspaceView["panelTab"]) => void;

  setAutosave: (cfg: Partial<AutosaveConfig>) => void;
  setRightPanelTab: (tab: RightPanelTab) => void;
}

const clamp = (v: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, Math.round(v)));

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => {
      /** aplica `fn` sobre a view do workspace ativo (criando-a se preciso). */
      const mutate = (fn: (v: WorkspaceView) => WorkspaceView): void => {
        set((s) => {
          const id = s.activeWorkspaceId;
          if (!id) return {};
          const current = s.byWorkspace[id] ?? DEFAULT_VIEW;
          return { byWorkspace: { ...s.byWorkspace, [id]: fn(current) } };
        });
      };

      return {
        activeWorkspaceId: null,
        byWorkspace: {},
        dirtyByPath: {},
        recentlyClosed: [],
        autosave: { enabled: false, intervalMs: 30_000 },
        rightPanelTab: "output",

        setActiveWorkspace: (id) =>
          set((s) => {
            if (s.activeWorkspaceId === id) return {};
            const byWorkspace =
              id && !s.byWorkspace[id]
                ? { ...s.byWorkspace, [id]: DEFAULT_VIEW }
                : s.byWorkspace;
            return {
              activeWorkspaceId: id,
              byWorkspace,
              dirtyByPath: {},
              recentlyClosed: [],
            };
          }),

        view: () => {
          const s = get();
          return (
            (s.activeWorkspaceId && s.byWorkspace[s.activeWorkspaceId]) ||
            DEFAULT_VIEW
          );
        },

        openTab: (path, kind) =>
          mutate((v) => {
            const existing = v.tabs.find((t) => t.path === path);
            if (existing) return { ...v, activeTab: path };
            const tab: WorkspaceTab = {
              path,
              kind: kind ?? kindFromPath(path),
              title: baseName(path),
            };
            return { ...v, tabs: [...v.tabs, tab], activeTab: path };
          }),

        closeTab: (path) => {
          const closed = get().view().tabs.find((t) => t.path === path);
          if (closed) {
            set((s) => ({
              recentlyClosed: [
                closed,
                ...s.recentlyClosed.filter((t) => t.path !== path),
              ].slice(0, 20),
            }));
          }
          mutate((v) => {
            const idx = v.tabs.findIndex((t) => t.path === path);
            if (idx < 0) return v;
            const tabs = v.tabs.filter((t) => t.path !== path);
            let activeTab = v.activeTab;
            if (activeTab === path) {
              const next = tabs[idx] ?? tabs[idx - 1] ?? null;
              activeTab = next?.path ?? null;
            }
            return { ...v, tabs, activeTab };
          });
          get().clearDirty(path);
        },

        closeOthers: (path) =>
          mutate((v) => ({
            ...v,
            tabs: v.tabs.filter((t) => t.path === path),
            activeTab: path,
          })),

        closeToRight: (path) =>
          mutate((v) => {
            const idx = v.tabs.findIndex((t) => t.path === path);
            if (idx < 0) return v;
            const tabs = v.tabs.slice(0, idx + 1);
            const activeTab =
              v.activeTab && tabs.some((t) => t.path === v.activeTab)
                ? v.activeTab
                : path;
            return { ...v, tabs, activeTab };
          }),

        closeAll: () => mutate((v) => ({ ...v, tabs: [], activeTab: null })),

        reopenClosed: () => {
          const [last, ...rest] = get().recentlyClosed;
          if (!last) return;
          set({ recentlyClosed: rest });
          get().openTab(last.path, last.kind);
        },

        reorderTabs: (from, to) =>
          mutate((v) => {
            if (
              from === to ||
              from < 0 ||
              to < 0 ||
              from >= v.tabs.length ||
              to >= v.tabs.length
            )
              return v;
            const tabs = [...v.tabs];
            const [moved] = tabs.splice(from, 1);
            tabs.splice(to, 0, moved!);
            return { ...v, tabs };
          }),

        setActiveTab: (path) => mutate((v) => ({ ...v, activeTab: path })),

        renameTabPath: (from, to) =>
          mutate((v) => {
            const tabs = v.tabs.map((t) =>
              t.path === from
                ? { ...t, path: to, title: baseName(to), kind: kindFromPath(to) }
                : t,
            );
            return {
              ...v,
              tabs,
              activeTab: v.activeTab === from ? to : v.activeTab,
            };
          }),

        toggleDir: (path) =>
          mutate((v) => ({
            ...v,
            expandedDirs: v.expandedDirs.includes(path)
              ? v.expandedDirs.filter((d) => d !== path)
              : [...v.expandedDirs, path],
          })),

        setExpanded: (path, expanded) =>
          mutate((v) => {
            const has = v.expandedDirs.includes(path);
            if (expanded === has) return v;
            return {
              ...v,
              expandedDirs: expanded
                ? [...v.expandedDirs, path]
                : v.expandedDirs.filter((d) => d !== path),
            };
          }),

        collapseAllDirs: () => mutate((v) => ({ ...v, expandedDirs: [] })),

        markDirty: (path, dirty) =>
          set((s) => {
            if (!!s.dirtyByPath[path] === dirty) return {};
            return { dirtyByPath: { ...s.dirtyByPath, [path]: dirty } };
          }),

        clearDirty: (path) =>
          set((s) => {
            if (!(path in s.dirtyByPath)) return {};
            const next = { ...s.dirtyByPath };
            delete next[path];
            return { dirtyByPath: next };
          }),

        setExplorerWidth: (px) =>
          mutate((v) => ({
            ...v,
            explorerWidth: clamp(px, EXPLORER_MIN, EXPLORER_MAX),
          })),

        toggleExplorer: (open) =>
          mutate((v) => ({
            ...v,
            explorerCollapsed: open == null ? !v.explorerCollapsed : !open,
          })),

        setPanelHeight: (px) =>
          mutate((v) => ({
            ...v,
            panelHeight: clamp(px, PANEL_MIN, PANEL_MAX),
          })),

        togglePanel: (open) =>
          mutate((v) => ({
            ...v,
            panelCollapsed: open == null ? !v.panelCollapsed : !open,
          })),

        setPanelTab: (tab) =>
          mutate((v) => ({ ...v, panelTab: tab, panelCollapsed: false })),

        setAutosave: (cfg) =>
          set((s) => ({ autosave: { ...s.autosave, ...cfg } })),

        setRightPanelTab: (tab) => set({ rightPanelTab: tab }),
      };
    },
    {
      name: "nbp.workspace",
      version: 1,
      partialize: (s) => ({
        byWorkspace: s.byWorkspace,
        autosave: s.autosave,
      }),
    },
  ),
);

/** Selector estável para a view do workspace ativo. */
export const selectView = (s: WorkspaceState): WorkspaceView =>
  (s.activeWorkspaceId && s.byWorkspace[s.activeWorkspaceId]) || DEFAULT_VIEW;
