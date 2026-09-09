import { useEffect, useMemo, useState } from "react";
import { useAuthContext } from "@/components/AuthProvider";
import { fileNodeIcon, fileTypeLabel } from "@/lib/fileIcons";
import { fileContextEntries, type FileMenuCallbacks } from "@/lib/fileMenu";
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
  currentDir: string;
  setCurrentDir: (path: string) => void;
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

function fmtSize(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const u = ["KB", "MB", "GB", "TB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${u[i]}`;
}

function fmtDate(epochSec: number | null | undefined): string {
  if (epochSec == null) return "—";
  return new Date(epochSec * 1000).toLocaleString();
}

type SortKey = "name" | "type" | "updated" | "size";

export function WorkspaceFileBrowser({
  root,
  loading,
  currentDir,
  setCurrentDir,
  openPaths,
  activePath,
  dirtyPaths,
  onRefresh,
  onMoveDrop,
  ...cb
}: Props) {
  const menuCb: FileMenuCallbacks = cb;
  const { user } = useAuthContext();
  const { open, menu } = useContextMenu();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "name", dir: 1 });
  const [dropTarget, setDropTarget] = useState<string | null>(null);

  const folder = useMemo(() => findDir(root, currentDir), [root, currentDir]);

  // se a pasta atual sumiu (delete/rename externo), volta para a Home
  useEffect(() => {
    if (root && currentDir && !folder) setCurrentDir("");
  }, [root, currentDir, folder, setCurrentDir]);

  const rows = useMemo(() => {
    const children = folder?.children ?? [];
    const q = query.trim().toLowerCase();
    const filtered = q ? children.filter((c) => c.name.toLowerCase().includes(q)) : children;
    const { key, dir } = sort;
    return [...filtered].sort((a, b) => {
      if (a.type !== b.type) return a.type === "dir" ? -1 : 1; // pastas primeiro
      let cmp = 0;
      if (key === "name") cmp = a.name.localeCompare(b.name);
      else if (key === "type") cmp = fileTypeLabel(a).localeCompare(fileTypeLabel(b));
      else if (key === "updated") cmp = (a.modified_at ?? 0) - (b.modified_at ?? 0);
      else if (key === "size") cmp = (a.size ?? 0) - (b.size ?? 0);
      return cmp * dir;
    });
  }, [folder, query, sort]);

  const crumbs = ["", ...currentDir.split("/").filter(Boolean).map((_, i, arr) =>
    arr.slice(0, i + 1).join("/"),
  )];

  const openNode = (node: FileNode): void => {
    if (node.type === "dir") setCurrentDir(node.path);
    else menuCb.onOpenFile(node.path);
  };

  const rowMenu = (e: React.MouseEvent, node: FileNode): void => {
    e.preventDefault();
    open(e, fileContextEntries(node, menuCb));
  };

  const headerBtn = (key: SortKey, label: string) => (
    <button
      type="button"
      className="flex items-center gap-1 hover:text-fg"
      onClick={() =>
        setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: 1 }))
      }
    >
      {label}
      {sort.key === key &&
        (sort.dir === 1 ? (
          <ChevronDownIcon className="h-3 w-3" />
        ) : (
          <ChevronRightIcon className="h-3 w-3 rotate-90" />
        ))}
    </button>
  );

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
        <div className="ml-auto flex items-center gap-1.5 rounded border border-surface-border px-2 py-1 text-xs">
          <SearchIcon className="h-3.5 w-3.5 text-fg-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar nesta pasta…"
            className="w-40 bg-transparent outline-none placeholder:text-fg-faint"
          />
        </div>
      </div>

      {/* breadcrumb */}
      <div className="flex h-8 shrink-0 items-center gap-1 px-3 text-xs text-fg-muted">
        {crumbs.map((c, idx) => (
          <span key={c || "home"} className="flex items-center gap-1">
            {idx > 0 && <ChevronRightIcon className="h-3 w-3 text-fg-faint" />}
            <button
              type="button"
              className={`rounded px-1 hover:bg-surface-variant ${
                idx === crumbs.length - 1 ? "font-medium text-fg" : ""
              } ${dropTarget === c ? "bg-primary/15 ring-1 ring-primary/40" : ""}`}
              onDragOver={(e) => {
                if (e.dataTransfer.types.includes(DND_MIME)) {
                  e.preventDefault();
                  setDropTarget(c);
                }
              }}
              onDragLeave={() => setDropTarget((t) => (t === c ? null : t))}
              onDrop={(e) => {
                e.preventDefault();
                setDropTarget(null);
                const src = e.dataTransfer.getData(DND_MIME);
                if (src) onMoveDrop(src, c);
              }}
              onClick={() => setCurrentDir(c)}
            >
              {idx === 0 ? "Home" : c.split("/").pop()}
            </button>
          </span>
        ))}
      </div>

      {/* table */}
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-surface text-left text-xs text-fg-faint">
            <tr className="border-b border-surface-border">
              <th className="px-3 py-1.5 font-medium">{headerBtn("name", "Nome")}</th>
              <th className="px-3 py-1.5 font-medium">{headerBtn("type", "Tipo")}</th>
              <th className="px-3 py-1.5 font-medium">Dono</th>
              <th className="px-3 py-1.5 font-medium">{headerBtn("updated", "Atualizado")}</th>
              <th className="px-3 py-1.5 text-right font-medium">{headerBtn("size", "Tamanho")}</th>
              <th className="w-8 px-2 py-1.5" />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-fg-faint">
                  Carregando…
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-xs text-fg-faint">
                  {currentDir ? "Pasta vazia." : "Sua Home está vazia — crie um arquivo ou pasta."}
                </td>
              </tr>
            )}
            {rows.map((node) => {
              const isActive = activePath === node.path;
              const isTabbed = openPaths.includes(node.path);
              const isDirty = !!dirtyPaths[node.path];
              return (
                <tr
                  key={node.path}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData(DND_MIME, node.path);
                    e.dataTransfer.effectAllowed = "move";
                  }}
                  onDragOver={
                    node.type === "dir"
                      ? (e) => {
                          if (e.dataTransfer.types.includes(DND_MIME)) {
                            e.preventDefault();
                            setDropTarget(node.path);
                          }
                        }
                      : undefined
                  }
                  onDragLeave={() => setDropTarget((t) => (t === node.path ? null : t))}
                  onDrop={
                    node.type === "dir"
                      ? (e) => {
                          e.preventDefault();
                          setDropTarget(null);
                          const src = e.dataTransfer.getData(DND_MIME);
                          if (src && src !== node.path) onMoveDrop(src, node.path);
                        }
                      : undefined
                  }
                  onDoubleClick={() => openNode(node)}
                  onContextMenu={(e) => rowMenu(e, node)}
                  className={`cursor-default border-b border-surface-border/60 ${
                    isActive
                      ? "bg-primary-container text-primary-on-container"
                      : dropTarget === node.path
                        ? "bg-primary/10 ring-1 ring-inset ring-primary/40"
                        : "hover:bg-surface-variant"
                  }`}
                >
                  <td className="px-3 py-1.5">
                    <button
                      type="button"
                      className="flex items-center gap-2 text-left"
                      onClick={() => openNode(node)}
                    >
                      {fileNodeIcon(node)}
                      <span className={`truncate ${isTabbed && !isActive ? "text-fg" : ""}`}>
                        {node.name}
                      </span>
                      {isDirty && <span className="text-warn">●</span>}
                    </button>
                  </td>
                  <td className="px-3 py-1.5 text-fg-muted">{fileTypeLabel(node)}</td>
                  <td className="px-3 py-1.5 text-fg-muted">{user?.name ?? "—"}</td>
                  <td className="px-3 py-1.5 text-fg-muted">{fmtDate(node.modified_at)}</td>
                  <td className="px-3 py-1.5 text-right text-fg-muted">
                    {node.type === "dir" ? "—" : fmtSize(node.size)}
                  </td>
                  <td className="px-2 py-1.5">
                    <button
                      type="button"
                      aria-label="Ações"
                      className="rounded p-0.5 text-fg-faint hover:bg-surface-variant hover:text-fg"
                      onClick={(e) => {
                        e.stopPropagation();
                        open(e, fileContextEntries(node, menuCb));
                      }}
                    >
                      <MoreIcon className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {menu}
    </div>
  );
}
