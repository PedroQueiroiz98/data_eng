import type { WorkspaceTab } from "@/store/workspace";
import { FilePreview } from "@/components/workspace/FilePreview";
import { WorkspaceDataTab } from "@/components/workspace/WorkspaceDataTab";
import { WorkspaceNotebookEditor } from "@/components/workspace/notebook/WorkspaceNotebookEditor";
import { EmptyState } from "@/ui";
import { WorkspaceIcon } from "@/ui/icons";

interface Props {
  workspaceId: string;
  tabs: WorkspaceTab[];
  activeTab: string | null;
  onDirtyChange: (path: string, dirty: boolean) => void;
}

/**
 * Área central. Mantém as abas montadas (uma por `path`), mostra só a ativa.
 * `notebook` → editor de células + kernel; `csv/parquet` → Data Viewer;
 * demais → Monaco (`FilePreview`).
 */
export function EditorSurface({ workspaceId, tabs, activeTab, onDirtyChange }: Props) {
  if (tabs.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          icon={WorkspaceIcon}
          title="Nenhum arquivo aberto"
          description="Escolha um arquivo no explorer ou use Ctrl+P."
        />
      </div>
    );
  }

  return (
    <div className="relative min-h-0 flex-1">
      {tabs.map((tab) => {
        const active = tab.path === activeTab;
        return (
          <div
            key={tab.path}
            className={active ? "absolute inset-0 flex flex-col" : "hidden"}
          >
            {tab.kind === "notebook" ? (
              <WorkspaceNotebookEditor
                workspaceId={workspaceId}
                path={tab.path}
                active={active}
                onDirtyChange={onDirtyChange}
              />
            ) : tab.kind === "csv" || tab.kind === "parquet" ? (
              <WorkspaceDataTab workspaceId={workspaceId} path={tab.path} />
            ) : (
              <FilePreview
                workspaceId={workspaceId}
                path={tab.path}
                active={active}
                onDirtyChange={onDirtyChange}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
