import { useRef } from "react";
import type { WorkspaceTab } from "@/store/workspace";
import { useContextMenu } from "@/ui/ContextMenu";
import { CloseIcon, FileIcon, NotebookIcon } from "@/ui/icons";

interface Props {
  tabs: WorkspaceTab[];
  activeTab: string | null;
  dirtyByPath: Record<string, boolean>;
  onSelect: (path: string) => void;
  onClose: (path: string) => void;
  onCloseOthers: (path: string) => void;
  onCloseRight: (path: string) => void;
  onCloseAll: () => void;
  onReopen: () => void;
  onReorder: (from: number, to: number) => void;
}

export function EditorTabs({
  tabs,
  activeTab,
  dirtyByPath,
  onSelect,
  onClose,
  onCloseOthers,
  onCloseRight,
  onCloseAll,
  onReopen,
  onReorder,
}: Props) {
  const { open, menu } = useContextMenu();
  const dragFrom = useRef<number | null>(null);

  return (
    <div className="flex min-h-9 items-stretch overflow-x-auto border-b border-surface-border bg-surface">
      {tabs.map((tab, idx) => {
        const active = tab.path === activeTab;
        const dirty = !!dirtyByPath[tab.path];
        const Icon = tab.kind === "notebook" ? NotebookIcon : FileIcon;
        return (
          <div
            key={tab.path}
            role="tab"
            aria-selected={active}
            title={tab.path}
            draggable
            onDragStart={() => (dragFrom.current = idx)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (dragFrom.current != null) onReorder(dragFrom.current, idx);
              dragFrom.current = null;
            }}
            onClick={() => onSelect(tab.path)}
            onAuxClick={(e) => {
              if (e.button === 1) onClose(tab.path);
            }}
            onContextMenu={(e) =>
              open(e, [
                { label: "Fechar", onClick: () => onClose(tab.path) },
                { label: "Fechar outras", onClick: () => onCloseOthers(tab.path) },
                { label: "Fechar à direita", onClick: () => onCloseRight(tab.path) },
                { label: "Fechar todas", onClick: onCloseAll },
                "separator",
                { label: "Reabrir aba fechada", onClick: onReopen },
              ])
            }
            className={`group flex cursor-pointer select-none items-center gap-1.5 border-r border-surface-border px-3 text-sm ${
              active
                ? "bg-surface-variant text-fg"
                : "text-fg-muted hover:bg-surface-variant/60"
            }`}
          >
            <Icon
              className={`h-3.5 w-3.5 shrink-0 ${
                tab.kind === "notebook" ? "text-primary" : "text-fg-faint"
              }`}
            />
            <span className="max-w-[12rem] truncate">{tab.title}</span>
            <button
              type="button"
              aria-label="Fechar aba"
              className="ml-0.5 rounded p-0.5 hover:bg-surface-border"
              onClick={(e) => {
                e.stopPropagation();
                onClose(tab.path);
              }}
            >
              {dirty ? (
                <span className="block h-2 w-2 rounded-full bg-warn group-hover:hidden" />
              ) : null}
              <CloseIcon
                className={`h-3.5 w-3.5 ${dirty ? "hidden group-hover:block" : ""}`}
              />
            </button>
          </div>
        );
      })}
      {menu}
    </div>
  );
}
