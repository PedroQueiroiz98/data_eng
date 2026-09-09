import { useEffect, useMemo, useState } from "react";
import { fileNodeIcon } from "@/lib/fileIcons";
import { fileContextEntries, type FileMenuCallbacks } from "@/lib/fileMenu";
import { dirName } from "@/lib/workspaceFiles";
import type { FileNode } from "@/lib/workspace";
import { useContextMenu } from "@/ui/ContextMenu";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FilePlusIcon,
  FolderPlusIcon,
  MoreIcon,
  NotebookIcon,
  RefreshIcon,
  SearchIcon,
  UploadIcon,
} from "@/ui/icons";

const DND_MIME = "application/x-nbp-path";

interface Props extends FileMenuCallbacks {
  root: FileNode | undefined;
  loading: boolean;
  /** pasta-alvo para "novo arquivo/pasta/upload" — o último nó de pasta clicado. */
  currentDir: string;
  setCurrentDir: (path: string) => void;
  /** pastas abertas na árvore (persistido por workspace, ver `store/workspace.ts`). */
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  openPaths: string[];
  activePath: string | null;
  dirtyPaths: Record<string, boolean>;
  onRefresh: () => void;
  onMoveDrop: (srcPath: string, destDir: string) => void;
}

function findDir(root: FileNode | undefined, path: string): FileNode | undefined {
  if (!root) return undefined;
  if (!path) return root;
  let node: FileNode | undefined = root;
  for (const seg of path.split("/").filter(Boolean)) {
    node = node?.children?.find((c) => c.type === "dir" && c.name === seg);
    if (!node) return undefined;
  }
  return node;
}

function sortNodes(nodes: FileNode[]): FileNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1; // pastas primeiro
    return a.name.localeCompare(b.name);
  });
}

/** Nós que batem a busca + seus ancestrais (pra manter o caminho visível/aberto). */
function matchTree(root: FileNode, q: string): Set<string> {
  const hit = new Set<string>();
  const walk = (n: FileNode): boolean => {
    let match = n.name.toLowerCase().includes(q);
    for (const c of n.children ?? []) {
      if (walk(c)) match = true;
    }
    if (match) hit.add(n.path);
    return match;
  };
  for (const c of root.children ?? []) walk(c);
  return hit;
}

export function WorkspaceFileBrowser({
  root,
  loading,
  currentDir,
  setCurrentDir,
  expandedDirs,
  onToggleDir,
  openPaths,
  activePath,
  dirtyPaths,
  onRefresh,
  onMoveDrop,
  ...cb
}: Props) {
  const menuCb: FileMenuCallbacks = cb;
  const { open, menu } = useContextMenu();
  const [query, setQuery] = useState("");
  const [dropTarget, setDropTarget] = useState<string | null>(null);

  // se a pasta-alvo sumiu (delete/rename externo), volta pro alvo ser a raiz
  useEffect(() => {
    if (root && currentDir && !findDir(root, currentDir)) setCurrentDir("");
  }, [root, currentDir, setCurrentDir]);

  const q = query.trim().toLowerCase();
  const matched = useMemo(() => (root && q ? matchTree(root, q) : null), [root, q]);
  const expandedSet = useMemo(() => new Set(expandedDirs), [expandedDirs]);

  const isOpen = (node: FileNode): boolean =>
    matched ? matched.has(node.path) : expandedSet.has(node.path);

  const openNode = (node: FileNode): void => {
    if (node.type === "dir") {
      setCurrentDir(node.path);
      if (!matched) onToggleDir(node.path);
    } else {
      setCurrentDir(dirName(node.path));
      menuCb.onOpenFile(node.path);
    }
  };

  const rowMenu = (e: React.MouseEvent, node: FileNode): void => {
    e.preventDefault();
    e.stopPropagation();
    open(e, fileContextEntries(node, menuCb));
  };

  const rows: React.ReactNode[] = [];
  const pushNode = (node: FileNode, depth: number): void => {
    if (matched && !matched.has(node.path)) return;
    const isDir = node.type === "dir";
    const open_ = isDir && isOpen(node);
    const isActive = activePath === node.path;
    const isSelected = !isActive && currentDir === node.path;
    const isTabbed = openPaths.includes(node.path);
    const isDirty = !!dirtyPaths[node.path];
    rows.push(
      <div
        key={node.path}
        draggable
        onDragStart={(e) => {
          e.dataTransfer.setData(DND_MIME, node.path);
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={
          isDir
            ? (e) => {
                if (e.dataTransfer.types.includes(DND_MIME)) {
                  e.preventDefault();
                  e.stopPropagation();
                  setDropTarget(node.path);
                }
              }
            : undefined
        }
        onDragLeave={() => setDropTarget((t) => (t === node.path ? null : t))}
        onDrop={
          isDir
            ? (e) => {
                e.preventDefault();
                e.stopPropagation();
                setDropTarget(null);
                const src = e.dataTransfer.getData(DND_MIME);
                if (src && src !== node.path) onMoveDrop(src, node.path);
              }
            : undefined
        }
        onClick={(e) => {
          e.stopPropagation();
          openNode(node);
        }}
        onContextMenu={(e) => rowMenu(e, node)}
        title={node.path}
        className={`group flex cursor-default items-center gap-1 rounded py-[3px] pr-1 text-[13px] ${
          isActive
            ? "bg-primary-container text-primary-on-container"
            : dropTarget === node.path
              ? "bg-primary/10 ring-1 ring-inset ring-primary/40"
              : isSelected
                ? "bg-surface-variant"
                : "hover:bg-surface-variant"
        }`}
        style={{ paddingLeft: 4 + depth * 16 }}
      >
        {isDir ? (
          <button
            type="button"
            tabIndex={-1}
            className="shrink-0 rounded p-0.5 text-fg-faint hover:text-fg"
            onClick={(e) => {
              e.stopPropagation();
              setCurrentDir(node.path);
              onToggleDir(node.path);
            }}
          >
            {open_ ? (
              <ChevronDownIcon className="h-3.5 w-3.5" />
            ) : (
              <ChevronRightIcon className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="w-[18px] shrink-0" />
        )}
        {fileNodeIcon(node)}
        <span className={`truncate ${isTabbed && !isActive ? "text-fg" : "text-fg-muted"}`}>
          {node.name}
        </span>
        {isDirty && <span className="text-warn">●</span>}
        <button
          type="button"
          aria-label="Ações"
          className="ml-auto hidden shrink-0 rounded p-0.5 text-fg-faint hover:bg-surface-variant hover:text-fg group-hover:block"
          onClick={(e) => rowMenu(e, node)}
        >
          <MoreIcon className="h-3.5 w-3.5" />
        </button>
      </div>,
    );
    if (isDir && open_) {
      for (const c of sortNodes(node.children ?? [])) pushNode(c, depth + 1);
    }
  };
  if (root) for (const c of sortNodes(root.children ?? [])) pushNode(c, 0);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* toolbar */}
      <div className="flex h-10 shrink-0 items-center gap-1 border-b border-surface-border px-2">
        <button
          type="button"
          title="Novo notebook"
          className="rounded p-1 text-fg-faint hover:bg-surface-variant hover:text-fg"
          onClick={() => cb.onNewNotebook(currentDir)}
        >
          <NotebookIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          title="Novo arquivo"
          className="rounded p-1 text-fg-faint hover:bg-surface-variant hover:text-fg"
          onClick={() => cb.onNewFile(currentDir)}
        >
          <FilePlusIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          title="Nova pasta"
          className="rounded p-1 text-fg-faint hover:bg-surface-variant hover:text-fg"
          onClick={() => cb.onNewFolder(currentDir)}
        >
          <FolderPlusIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          title="Enviar arquivo"
          className="rounded p-1 text-fg-faint hover:bg-surface-variant hover:text-fg"
          onClick={() => cb.onUpload(currentDir)}
        >
          <UploadIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          title="Recarregar"
          className="rounded p-1 text-fg-faint hover:bg-surface-variant hover:text-fg"
          onClick={onRefresh}
        >
          <RefreshIcon className="h-4 w-4" />
        </button>
      </div>

      {/* busca */}
      <div className="flex h-9 shrink-0 items-center gap-1.5 border-b border-surface-border px-2">
        <div className="flex w-full items-center gap-1.5 rounded border border-surface-border px-2 py-1 text-xs">
          <SearchIcon className="h-3.5 w-3.5 shrink-0 text-fg-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar no workspace…"
            className="w-full bg-transparent outline-none placeholder:text-fg-faint"
          />
        </div>
      </div>

      {/* árvore */}
      <div
        className="min-h-0 flex-1 overflow-auto py-1"
        onClick={() => setCurrentDir("")}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes(DND_MIME)) {
            e.preventDefault();
            setDropTarget("");
          }
        }}
        onDragLeave={() => setDropTarget((t) => (t === "" ? null : t))}
        onDrop={(e) => {
          e.preventDefault();
          setDropTarget(null);
          const src = e.dataTransfer.getData(DND_MIME);
          if (src) onMoveDrop(src, "");
        }}
      >
        {loading && (
          <div className="px-3 py-6 text-center text-xs text-fg-faint">Carregando…</div>
        )}
        {!loading && rows.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-fg-faint">
            {q ? "Nenhum resultado." : "Sua Home está vazia — crie um arquivo ou pasta."}
          </div>
        )}
        {rows}
      </div>
      {menu}
    </div>
  );
}
