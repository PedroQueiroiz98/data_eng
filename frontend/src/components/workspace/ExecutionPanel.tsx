import { useEffect, useRef } from "react";
import { AiChatPanel } from "@/components/assistant/AiChatPanel";
import { GitPanel } from "@/components/workspace/GitPanel";
import { useResizable } from "@/hooks/useResizable";
import { selectView, useWorkspaceStore, type WorkspaceView } from "@/store/workspace";
import { useWorkspaceRuntime } from "@/store/workspaceRuntime";
import { CloseIcon } from "@/ui/icons";

const TABS: { id: WorkspaceView["panelTab"]; label: string }[] = [
  { id: "execution", label: "Execution" },
  { id: "output", label: "Output" },
  { id: "problems", label: "Problems" },
  { id: "git", label: "Git" },
  { id: "assistant", label: "✨ AI" },
];

export function ExecutionPanel({ workspaceId }: { workspaceId: string }) {
  const view = useWorkspaceStore(selectView);
  const setPanelTab = useWorkspaceStore((s) => s.setPanelTab);
  const togglePanel = useWorkspaceStore((s) => s.togglePanel);
  const setPanelHeight = useWorkspaceStore((s) => s.setPanelHeight);

  const resize = useResizable({
    axis: "y",
    value: view.panelHeight,
    min: 120,
    max: 640,
    invert: true,
    onChange: setPanelHeight,
  });

  if (view.panelCollapsed) {
    return (
      <div className="flex h-7 shrink-0 items-center gap-2 border-t border-surface-border bg-surface px-3 text-xs text-fg-muted">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className="hover:text-fg"
            onClick={() => setPanelTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div
      className="flex shrink-0 flex-col border-t border-surface-border bg-surface"
      style={{ height: view.panelHeight }}
    >
      <div
        {...resize.handleProps}
        className={`h-1 cursor-row-resize bg-surface-border hover:bg-primary/40 ${
          resize.dragging ? "bg-primary/60" : ""
        }`}
      />
      <div className="flex h-8 items-center gap-1 border-b border-surface-border px-2 text-xs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setPanelTab(t.id)}
            className={`rounded px-2 py-0.5 ${
              view.panelTab === t.id
                ? "bg-primary-container text-primary-on-container"
                : "text-fg-muted hover:bg-surface-variant"
            }`}
          >
            {t.label}
          </button>
        ))}
        <button
          type="button"
          className="ml-auto rounded p-0.5 text-fg-faint hover:bg-surface-variant"
          title="Fechar painel"
          onClick={() => togglePanel(false)}
        >
          <CloseIcon className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {view.panelTab === "execution" && <ExecutionTab />}
        {view.panelTab === "output" && <OutputTab />}
        {view.panelTab === "problems" && (
          <p className="p-3 text-xs text-fg-faint">
            Diagnósticos do notebook ativo aparecem aqui.
          </p>
        )}
        {view.panelTab === "git" && <GitPanel workspaceId={workspaceId} />}
        {view.panelTab === "assistant" && <AiChatPanel />}
      </div>
    </div>
  );
}

function ExecutionTab() {
  const timeline = useWorkspaceRuntime((s) => s.timeline);
  const kernelStatus = useWorkspaceRuntime((s) => s.kernelStatus);
  const total = timeline
    .filter((t) => t.status !== "running")
    .reduce((acc, t) => acc + (t.durationMs ?? 0), 0);

  return (
    <div className="p-3 font-mono text-xs">
      <div className="text-fg-muted">
        Kernel: <span className="text-fg">{kernelStatus}</span>
      </div>
      {timeline.length === 0 ? (
        <p className="mt-2 text-fg-faint">Nenhuma execução ainda.</p>
      ) : (
        <div className="mt-1 space-y-0.5">
          {timeline.map((t, i) => (
            <div key={`${t.cellId}-${i}`} className="flex items-center gap-2">
              <span
                className={
                  t.status === "ok"
                    ? "text-ok"
                    : t.status === "error"
                      ? "text-danger"
                      : "text-info"
                }
              >
                {t.status === "ok" ? "✓" : t.status === "error" ? "✕" : "⏳"}
              </span>
              <span className="text-fg-muted">Célula {i + 1}</span>
              <span className="ml-auto text-fg-faint">
                {t.durationMs != null ? `${(t.durationMs / 1000).toFixed(2)}s` : "…"}
              </span>
            </div>
          ))}
          <div className="mt-1 border-t border-surface-border pt-1 text-fg-muted">
            Total: {(total / 1000).toFixed(2)}s
          </div>
        </div>
      )}
    </div>
  );
}

function OutputTab() {
  const logLines = useWorkspaceRuntime((s) => s.logLines);
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [logLines.length]);

  return (
    <pre
      ref={ref}
      className="h-full overflow-auto bg-zinc-950 p-3 font-mono text-xs text-zinc-100"
    >
      {logLines.length === 0
        ? "Sem saída técnica."
        : logLines.map((l) => (
            <div key={l.seq} className={l.level === "error" ? "text-red-400" : ""}>
              {l.text}
            </div>
          ))}
    </pre>
  );
}
