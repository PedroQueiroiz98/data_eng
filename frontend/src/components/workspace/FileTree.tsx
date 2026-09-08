import { useMemo, useState } from "react";
import type { FileNode } from "@/lib/workspace";
import { kindFromPath } from "@/lib/workspaceFiles";
import { useContextMenu, type ContextMenuEntry } from "@/ui/ContextMenu";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  DeleteIcon,
  DownloadIcon,
  DuplicateIcon,
  EditIcon,
  FileIcon,
  FilePlusIcon,
  FolderIcon,
  FolderOpenIcon,
  FolderPlusIcon,
  MoreIcon,
  NotebookIcon,
  RunIcon,
  UploadIcon,
} from "@/ui/icons";

export interface FileTreeCallbacks {
  onOpenFile: (path: string, opts?: { newTab?: boolean }) => void;
  onNewNotebook: (parentDir: string) => void;
  onNewFile: (parentDir: string) => void;
  onNewFolder: (parentDir: string) => void;
  onUpload: (parentDir: string) => void;
  onRename: (node: FileNode) => void;
  onMove: (node: FileNode) => void;
  onDuplicate: (node: FileNode) => void;
  onDelete: (node: FileNode) => void;
  onDownload: (node: FileNode) => void;
  onCopyPath: (node: FileNode, relative: boolean) => void;
  onRun: (node: FileNode) => void;
  onExport: (node: FileNode) => void;
  onMoveDrop: (srcPath: string, destDir: string) => void;
}

interface Props extends FileTreeCallbacks {
  root: FileNode;
  openPaths: string[];
  activePath: string | null;
  dirtyPaths: Record<string, boolean>;
  expanded: Set<string>;
  onToggleDir: (path: string) => void;
  filter: string;
}

const DND_MIME = "application/x-nbp-path";

const isNotebook = (path: string): boolean => kindFromPath(path) === "notebook";

function entriesFor(node: FileNode, cb: FileTreeCallbacks): ContextMenuEntry[] {
  const i = (Icon: typeof FileIcon) => <Icon className="h-4 w-4" />;
  if (node.type === "dir") {
    return [
      { label: "Novo notebook", icon: i(NotebookIcon), onClick: () => cb.onNewNotebook(node.path) },
      { label: "Novo arquivo", icon: i(FilePlusIcon), onClick: () => cb.onNewFile(node.path) },
      { label: "Nova pasta", icon: i(FolderPlusIcon), onClick: () => cb.onNewFolder(node.path) },
      { label: "Enviar arquivo", icon: i(UploadIcon), onClick: () => cb.onUpload(node.path) },
      "separator",
      { label: "Copiar caminho", onClick: () => cb.onCopyPath(node, false) },
      { label: "Copiar caminho relativo", onClick: () => cb.onCopyPath(node, true) },
      "separator",
      { label: "Renomear", icon: i(EditIcon), onClick: () => cb.onRename(node) },
      { label: "Mover", onClick: () => cb.onMove(node) },
      { label: "Baixar (zip)", icon: i(DownloadIcon), onClick: () => cb.onDownload(node) },
      { label: "Excluir", icon: i(DeleteIcon), danger: true, onClick: () => cb.onDelete(node) },
    ];
  }
  const common: ContextMenuEntry[] = [
    { label: "Abrir", onClick: () => cb.onOpenFile(node.path) },
    { label: "Abrir em nova aba", onClick: () => cb.onOpenFile(node.path, { newTab: true }) },
  ];
  if (isNotebook(node.path)) {
    return [
      ...common,
      { label: "Executar", icon: i(RunIcon), onClick: () => cb.onRun(node) },
      { label: "Exportar", icon: i(DownloadIcon), onClick: () => cb.onExport(node) },
      "separator",
      { label: "Copiar caminho", onClick: () => cb.onCopyPath(node, false) },
      { label: "Copiar caminho relativo", onClick: () => cb.onCopyPath(node, true) },
      "separator",
      { label: "Renomear", icon: i(EditIcon), onClick: () => cb.onRename(node) },
      { label: "Duplicar", icon: i(DuplicateIcon), onClick: () => cb.onDuplicate(node) },
      { label: "Excluir", icon: i(DeleteIcon), danger: true, onClick: () => cb.onDelete(node) },
    ];
  }
  return [
    ...common,
    "separator",
    { label: "Copiar caminho", onClick: () => cb.onCopyPath(node, false) },
    { label: "Copiar caminho relativo", onClick: () => cb.onCopyPath(node, true) },
    "separator",
    { label: "Renomear", icon: i(EditIcon), onClick: () => cb.onRename(node) },
    { label: "Mover", onClick: () => cb.onMove(node) },
    { label: "Duplicar", icon: i(DuplicateIcon), onClick: () => cb.onDuplicate(node) },
    { label: "Baixar", icon: i(DownloadIcon), onClick: () => cb.onDownload(node) },
    { label: "Excluir", icon: i(DeleteIcon), danger: true, onClick: () => cb.onDelete(node) },
  ];
}

function flatten(node: FileNode, acc: FileNode[]): void {
  for (const c of node.children ?? []) {
    if (c.type === "file") acc.push(c);
    else flatten(c, acc);
  }
}

export function FileTree({ root, filter, ...rest }: Props) {
  const { open, menu } = useContextMenu();
  const cb = rest as FileTreeCallbacks;

  const children = useMemo(() => sortNodes(root.children ?? []), [root]);

  const results = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return null;
    const all: FileNode[] = [];
    flatten(root, all);
    return all
      .filter((f) => f.path.toLowerCase().includes(q))
      .sort((a, b) => a.path.localeCompare(b.path))
      .slice(0, 200);
  }, [filter, root]);

  if (results) {
    return (
      <div className="select-none py-1 text-sm">
        {results.length === 0 && (
          <p className="px-3 py-2 text-xs text-fg-faint">Nenhum arquivo encontrado.</p>
        )}
        {results.map((node) => (
          <div
            key={node.path}
            className="group flex items-center gap-1.5 rounded px-2 py-1 hover:bg-surface-variant"
            onClick={() => cb.onOpenFile(node.path)}
            onContextMenu={(e) => open(e, entriesFor(node, cb))}
          >
            <FileGlyph path={node.path} />
            <span className="truncate">{node.name}</span>
            <span className="ml-auto truncate text-[11px] text-fg-faint">{node.path}</span>
          </div>
        ))}
        {menu}
      </div>
    );
  }

  return (
    <div
      className="select-none py-1 text-sm"
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes(DND_MIME)) e.preventDefault();
      }}
      onDrop={(e) => {
        const src = e.dataTransfer.getData(DND_MIME);
        if (src) cb.onMoveDrop(src, "");
      }}
    >
      {children.length === 0 && (
        <p className="px-3 py-2 text-xs text-fg-faint">Workspace vazio.</p>
      )}
      {children.map((node) => (
        <TreeNode key={node.path} node={node} depth={0} openMenu={open} {...rest} />
      ))}
      {menu}
    </div>
  );
}

interface NodeProps extends FileTreeCallbacks {
  node: FileNode;
  depth: number;
  openPaths: string[];
  activePath: string | null;
  dirtyPaths: Record<string, boolean>;
  expanded: Set<string>;
  onToggleDir: (path: string) => void;
  openMenu: (e: React.MouseEvent, entries: ContextMenuEntry[]) => void;
}

function TreeNode(props: NodeProps) {
  const { node, depth, openPaths, activePath, dirtyPaths, expanded, onToggleDir, openMenu } = props;
  const cb = props as FileTreeCallbacks;
  const isDir = node.type === "dir";
  const isOpen = expanded.has(node.path);
  const isActive = activePath === node.path;
  const isTabbed = openPaths.includes(node.path);
  const isDirty = !!dirtyPaths[node.path];
  const [dropInto, setDropInto] = useState(false);
  const pad = { paddingLeft: `${depth * 14 + 8}px` };

  const entries = entriesFor(node, cb);

  return (
    <div>
      <div
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
                  setDropInto(true);
                }
              }
            : undefined
        }
        onDragLeave={isDir ? () => setDropInto(false) : undefined}
        onDrop={
          isDir
            ? (e) => {
                e.preventDefault();
                e.stopPropagation();
                setDropInto(false);
                const src = e.dataTransfer.getData(DND_MIME);
                if (src && src !== node.path) cb.onMoveDrop(src, node.path);
              }
            : undefined
        }
        onContextMenu={(e) => openMenu(e, entries)}
        className={`group flex items-center gap-1 rounded pr-1 ${
          isActive
            ? "bg-primary-container text-primary-on-container"
            : dropInto
              ? "bg-primary/15 ring-1 ring-primary/40"
              : "hover:bg-surface-variant"
        }`}
      >
        <button
          type="button"
          style={pad}
          className="flex min-w-0 flex-1 items-center gap-1.5 py-1 text-left"
          onClick={() =>
            isDir ? onToggleDir(node.path) : cb.onOpenFile(node.path)
          }
          onDoubleClick={() => !isDir && cb.onOpenFile(node.path, { newTab: true })}
        >
          {isDir ? (
            <>
              {isOpen ? (
                <ChevronDownIcon className="h-3.5 w-3.5 shrink-0 text-fg-faint" />
              ) : (
                <ChevronRightIcon className="h-3.5 w-3.5 shrink-0 text-fg-faint" />
              )}
              {isOpen ? (
                <FolderOpenIcon className="h-4 w-4 shrink-0 text-fg-muted" />
              ) : (
                <FolderIcon className="h-4 w-4 shrink-0 text-fg-muted" />
              )}
            </>
          ) : (
            <>
              <span className="w-3.5 shrink-0" />
              <FileGlyph path={node.path} />
            </>
          )}
          <span className={`truncate ${isTabbed && !isActive ? "text-fg" : ""}`}>
            {node.name}
          </span>
          {isDirty && <span className="ml-1 text-warn">●</span>}
        </button>
        <button
          type="button"
          aria-label="Mais ações"
          className="rounded p-0.5 opacity-0 transition hover:bg-surface-variant group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            openMenu(e, entries);
          }}
        >
          <MoreIcon className="h-4 w-4 text-fg-faint" />
        </button>
      </div>

      {isDir && isOpen && (
        <div>
          {sortNodes(node.children ?? []).map((child) => (
            <TreeNode key={child.path} {...props} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function FileGlyph({ path }: { path: string }) {
  const Icon = isNotebook(path) ? NotebookIcon : FileIcon;
  return (
    <Icon
      className={`h-4 w-4 shrink-0 ${isNotebook(path) ? "text-primary" : "text-fg-faint"}`}
    />
  );
}

function sortNodes(nodes: FileNode[]): FileNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}
