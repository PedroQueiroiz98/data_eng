import { useEffect, useMemo, useState } from "react";
import type { FileNode } from "@/lib/workspace";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { ChevronDownIcon, ChevronRightIcon, FolderIcon, FolderOpenIcon } from "@/ui/icons";

interface Props {
  open: boolean;
  root: FileNode | undefined;
  /** Paths de origem: não é possível mover algo para dentro de si mesmo/descendente. */
  excludePrefixes: string[];
  initialDir?: string;
  onClose: () => void;
  onConfirm: (destDir: string) => void;
}

function sortDirs(nodes: FileNode[] | null | undefined): FileNode[] {
  return (nodes ?? [])
    .filter((n) => n.type === "dir")
    .sort((a, b) => a.name.localeCompare(b.name));
}

function isBlocked(path: string, excludePrefixes: string[]): boolean {
  return excludePrefixes.some((p) => path === p || path.startsWith(`${p}/`));
}

export function FolderPickerDialog({
  open,
  root,
  excludePrefixes,
  initialDir = "",
  onClose,
  onConfirm,
}: Props) {
  const [dest, setDest] = useState(initialDir);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (open) {
      setDest(isBlocked(initialDir, excludePrefixes) ? "" : initialDir);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const rows = useMemo(() => {
    const out: { path: string; name: string; depth: number; blocked: boolean }[] = [];
    const walk = (node: FileNode, depth: number) => {
      const blocked = isBlocked(node.path, excludePrefixes);
      out.push({ path: node.path, name: node.name, depth, blocked });
      if (!blocked && expanded.has(node.path)) {
        for (const child of sortDirs(node.children)) walk(child, depth + 1);
      }
    };
    for (const child of sortDirs(root?.children)) walk(child, 0);
    return out;
  }, [root, expanded, excludePrefixes]);

  const toggle = (path: string) =>
    setExpanded((s) => {
      const next = new Set(s);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Mover para pasta"
      width="sm"
      footer={
        <>
          <Button variant="text" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            onClick={() => {
              onConfirm(dest);
              onClose();
            }}
          >
            Mover para "{dest || "/"}"
          </Button>
        </>
      }
    >
      <div className="max-h-80 overflow-auto rounded border border-surface-border p-1 text-sm">
        <div
          role="button"
          tabIndex={0}
          onClick={() => setDest("")}
          className={`flex cursor-pointer items-center gap-1.5 rounded px-2 py-1 ${
            dest === "" ? "bg-primary-container text-primary-on-container" : "hover:bg-surface-variant"
          }`}
        >
          <FolderOpenIcon className="h-3.5 w-3.5 shrink-0 text-fg-faint" />
          <span>Home (raiz)</span>
        </div>
        {rows.map((row) => (
          <div
            key={row.path}
            role="button"
            tabIndex={row.blocked ? -1 : 0}
            aria-disabled={row.blocked}
            onClick={() => !row.blocked && setDest(row.path)}
            title={row.blocked ? "Não é possível mover para dentro do próprio item" : row.path}
            className={`flex items-center gap-1 rounded py-1 pr-2 ${
              row.blocked
                ? "cursor-not-allowed text-fg-faint/50"
                : dest === row.path
                  ? "cursor-pointer bg-primary-container text-primary-on-container"
                  : "cursor-pointer hover:bg-surface-variant"
            }`}
            style={{ paddingLeft: 8 + row.depth * 16 }}
          >
            <button
              type="button"
              tabIndex={-1}
              disabled={row.blocked}
              className="shrink-0 rounded p-0.5 text-fg-faint hover:text-fg disabled:hover:text-fg-faint"
              onClick={(e) => {
                e.stopPropagation();
                toggle(row.path);
              }}
            >
              {expanded.has(row.path) ? (
                <ChevronDownIcon className="h-3.5 w-3.5" />
              ) : (
                <ChevronRightIcon className="h-3.5 w-3.5" />
              )}
            </button>
            <FolderIcon className="h-3.5 w-3.5 shrink-0 text-fg-faint" />
            <span className="truncate">{row.name}</span>
          </div>
        ))}
        {rows.length === 0 && (
          <div className="px-2 py-4 text-center text-xs text-fg-faint">Nenhuma subpasta.</div>
        )}
      </div>
    </Dialog>
  );
}
