import { useMemo, useState } from "react";
import { useWorkspaceTree } from "@/hooks/useWorkspace";
import { type FileNode } from "@/lib/workspace";
import { Dialog } from "@/ui";
import { NotebookIcon, SearchIcon, SpinnerIcon } from "@/ui/icons";

interface NbEntry {
  path: string;
  name: string;
  folder: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onPick: (e: { notebookPath: string; label: string }) => void;
}

function collectIpynb(node: FileNode, acc: NbEntry[]): void {
  for (const child of node.children ?? []) {
    if (child.type === "dir") {
      collectIpynb(child, acc);
    } else if (child.path.toLowerCase().endsWith(".ipynb")) {
      const slash = child.path.lastIndexOf("/");
      acc.push({
        path: child.path,
        name: child.name,
        folder: slash >= 0 ? `/root/${child.path.slice(0, slash)}` : "/root",
      });
    }
  }
}

export function WorkspaceNotebookPicker({ open, onClose, onPick }: Props) {
  const tree = useWorkspaceTree();
  const [query, setQuery] = useState("");

  const entries = useMemo(() => {
    const acc: NbEntry[] = [];
    if (tree.data) collectIpynb(tree.data, acc);
    const q = query.trim().toLowerCase();
    return (q ? acc.filter((e) => e.path.toLowerCase().includes(q)) : acc)
      .sort((a, b) => a.path.localeCompare(b.path))
      .slice(0, 400);
  }, [tree.data, query]);

  const loading = open && tree.isLoading;

  return (
    <Dialog open={open} onClose={onClose} title="Escolher notebook do Workspace" width="lg">
      <div className="mb-2 flex items-center gap-2 rounded border border-surface-border px-2 py-1.5 text-sm">
        <SearchIcon className="h-4 w-4 text-fg-faint" />
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar notebook…"
          className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-fg-faint"
        />
      </div>

      <div className="max-h-[50vh] overflow-auto">
        {loading && (
          <div className="flex justify-center py-6 text-fg-faint">
            <SpinnerIcon className="h-5 w-5 animate-spin" />
          </div>
        )}
        {!loading && entries.length === 0 && (
          <p className="px-2 py-4 text-sm text-fg-faint">
            Nenhum notebook (.ipynb) encontrado em /root.
          </p>
        )}
        {entries.map((e) => (
          <button
            key={e.path}
            type="button"
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-surface-variant"
            onClick={() => {
              onPick({ notebookPath: e.path, label: e.name });
              onClose();
            }}
          >
            <NotebookIcon className="h-4 w-4 shrink-0 text-primary" />
            <span className="truncate">{e.name}</span>
            <span className="ml-auto truncate text-xs text-fg-faint">{e.folder}</span>
          </button>
        ))}
      </div>
    </Dialog>
  );
}
