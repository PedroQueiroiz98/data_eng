import { useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { useWorkspaces } from "@/hooks/useWorkspace";
import { getTree, type FileNode } from "@/lib/workspace";
import { Dialog } from "@/ui";
import { NotebookIcon, SearchIcon, SpinnerIcon } from "@/ui/icons";

interface NbEntry {
  workspaceId: string;
  workspaceName: string;
  path: string;
  name: string;
  folder: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onPick: (e: { workspaceId: string; notebookPath: string; label: string }) => void;
}

function collectIpynb(
  node: FileNode,
  wsId: string,
  wsName: string,
  acc: NbEntry[],
): void {
  for (const child of node.children ?? []) {
    if (child.type === "dir") {
      collectIpynb(child, wsId, wsName, acc);
    } else if (child.path.toLowerCase().endsWith(".ipynb")) {
      const slash = child.path.lastIndexOf("/");
      acc.push({
        workspaceId: wsId,
        workspaceName: wsName,
        path: child.path,
        name: child.name,
        folder: slash >= 0 ? child.path.slice(0, slash) : "/",
      });
    }
  }
}

export function WorkspaceNotebookPicker({ open, onClose, onPick }: Props) {
  const workspaces = useWorkspaces();
  const list = useMemo(() => workspaces.data ?? [], [workspaces.data]);
  const [query, setQuery] = useState("");

  const trees = useQueries({
    queries: list.map((ws) => ({
      queryKey: ["workspaces", ws.id, "tree", ""],
      queryFn: () => getTree(ws.id),
      enabled: open,
      staleTime: 30_000,
    })),
  });

  const entries = useMemo(() => {
    const acc: NbEntry[] = [];
    list.forEach((ws, i) => {
      const tree = trees[i]?.data;
      if (tree) collectIpynb(tree, ws.id, ws.name, acc);
    });
    const q = query.trim().toLowerCase();
    return (q ? acc.filter((e) => `${e.workspaceName}/${e.path}`.toLowerCase().includes(q)) : acc)
      .sort((a, b) => `${a.workspaceName}/${a.path}`.localeCompare(`${b.workspaceName}/${b.path}`))
      .slice(0, 400);
  }, [list, trees, query]);

  const loading = open && trees.some((t) => t.isLoading);

  const grouped = useMemo(() => {
    const m = new Map<string, NbEntry[]>();
    for (const e of entries) {
      const bucket = m.get(e.workspaceName);
      if (bucket) bucket.push(e);
      else m.set(e.workspaceName, [e]);
    }
    return [...m.entries()];
  }, [entries]);

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
            Nenhum notebook encontrado nos Workspaces.
          </p>
        )}
        {grouped.map(([wsName, items]) => (
          <div key={wsName} className="mb-2">
            <div className="px-1 py-1 text-xs font-semibold uppercase tracking-wide text-fg-faint">
              {wsName}
            </div>
            {items.map((e) => (
              <button
                key={`${e.workspaceId}:${e.path}`}
                type="button"
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-surface-variant"
                onClick={() => {
                  onPick({
                    workspaceId: e.workspaceId,
                    notebookPath: e.path,
                    label: e.name,
                  });
                  onClose();
                }}
              >
                <NotebookIcon className="h-4 w-4 shrink-0 text-primary" />
                <span className="truncate">{e.name}</span>
                <span className="ml-auto truncate text-xs text-fg-faint">{e.folder}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </Dialog>
  );
}
