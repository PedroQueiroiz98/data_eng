import { Link } from "react-router-dom";
import type { WorkspaceDetail } from "@/lib/workspace";
import { BackIcon, BranchIcon } from "@/ui/icons";

interface Props {
  workspace: WorkspaceDetail;
  dirtyCount: number;
}

export function WorkspaceHeader({ workspace, dirtyCount }: Props) {
  const git = workspace.git_repository;
  return (
    <div className="flex h-12 shrink-0 items-center gap-3 border-b border-surface-border bg-surface px-3">
      <Link
        to="/workspaces"
        className="flex items-center gap-1 rounded px-1.5 py-1 text-sm text-fg-muted hover:bg-surface-variant"
      >
        <BackIcon className="h-4 w-4" />
        Workspaces
      </Link>
      <span className="text-fg-faint">/</span>
      <span className="truncate font-medium text-fg">{workspace.name}</span>
      <span className="rounded bg-surface-variant px-1.5 py-0.5 text-[11px] text-fg-muted">
        {workspace.slug}
      </span>
      {!workspace.is_active && (
        <span className="rounded bg-danger/10 px-1.5 py-0.5 text-[11px] text-danger">
          inativo
        </span>
      )}

      <div className="ml-auto flex items-center gap-3 text-xs text-fg-muted">
        <span className="flex items-center gap-1">
          <BranchIcon className="h-3.5 w-3.5" />
          {git?.current_branch ?? git?.default_branch ?? "sem Git"}
        </span>
        {dirtyCount > 0 && (
          <span className="text-amber-600 dark:text-amber-400">
            {dirtyCount} não salvo{dirtyCount > 1 ? "s" : ""}
          </span>
        )}
      </div>
    </div>
  );
}
