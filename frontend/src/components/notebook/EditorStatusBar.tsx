import { useEffect, useState } from "react";
import { lspHealth, type LspHealth } from "@/lib/lsp";
import { useEditorConfig } from "@/lib/editorConfig";
import { FailIcon, SuccessIcon, WarnIcon } from "@/ui/icons";

interface Props {
  problems: { errors: number; warnings: number };
  onProblemsClick?: () => void;
}

const POLL_MS = 20_000;

export function EditorStatusBar({ problems, onProblemsClick }: Props) {
  const [health, setHealth] = useState<LspHealth | null>(null);
  const aiEnabled = useEditorConfig((s) => s.config.ai.enabled);
  const lspOn = useEditorConfig((s) => s.config.editor.autocomplete || s.config.editor.diagnostics);

  useEffect(() => {
    let alive = true;
    const tick = () => {
      void lspHealth().then((h) => alive && setHealth(h));
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const ready = !!health?.ready && lspOn;
  const envName = health?.environment_path
    ? health.environment_path.split(/[\\/]/).filter(Boolean).slice(-2).join("/")
    : "—";

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-b border border-t-0 border-surface-border bg-surface-variant px-3 py-1.5 text-xs text-fg-muted">
      <span>Python {health?.python_version || "—"}</span>
      <span className="hidden sm:inline">Env: {envName}</span>
      <Dot ok={ready} label={`LSP: ${!lspOn ? "Desativado" : ready ? "Pronto" : "Offline"}`} />
      <span>Kernel: —</span>
      <span>DB: —</span>
      <Dot ok={aiEnabled} label={`IA: ${aiEnabled ? "Ativa" : "Desativada"}`} muted={!aiEnabled} />
      <button
        type="button"
        onClick={onProblemsClick}
        className="ml-auto inline-flex items-center gap-2 rounded px-1.5 py-0.5 hover:bg-surface"
      >
        <span className="inline-flex items-center gap-1 text-danger">
          <FailIcon className="h-3.5 w-3.5" />
          {problems.errors}
        </span>
        <span className="inline-flex items-center gap-1 text-warn">
          <WarnIcon className="h-3.5 w-3.5" />
          {problems.warnings}
        </span>
      </button>
    </div>
  );
}

function Dot({ ok, label, muted }: { ok: boolean; label: string; muted?: boolean }) {
  const Icon = ok ? SuccessIcon : muted ? WarnIcon : FailIcon;
  const cls = ok ? "text-ok" : muted ? "text-fg-faint" : "text-danger";
  return (
    <span className={`inline-flex items-center gap-1 ${cls}`}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}
