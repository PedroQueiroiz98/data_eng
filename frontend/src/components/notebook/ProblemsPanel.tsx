import { type LspDiagnostic } from "@/lib/lsp";
import { FailIcon, InfoIcon, WarnIcon } from "@/ui/icons";

interface Props {
  diagnostics: LspDiagnostic[];
  onSelect?: (cellIndex: number, line: number, column: number) => void;
  onClose?: () => void;
}

const ICON = {
  error: { Icon: FailIcon, cls: "text-danger" },
  warning: { Icon: WarnIcon, cls: "text-warn" },
  information: { Icon: InfoIcon, cls: "text-info" },
  hint: { Icon: InfoIcon, cls: "text-fg-muted" },
} as const;

export function ProblemsPanel({ diagnostics, onSelect, onClose }: Props) {
  return (
    <div className="surface mt-3">
      <div className="flex items-center justify-between border-b border-surface-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-fg-faint">
        <span>Problemas ({diagnostics.length})</span>
        {onClose && (
          <button type="button" onClick={onClose} className="text-fg-muted hover:text-fg">
            fechar
          </button>
        )}
      </div>
      {diagnostics.length === 0 ? (
        <p className="px-3 py-4 text-sm text-fg-faint">Nenhum problema detectado.</p>
      ) : (
        <ul className="max-h-64 divide-y divide-surface-border overflow-y-auto text-sm">
          {diagnostics.map((d, i) => {
            const { Icon, cls } = ICON[d.severity] ?? ICON.information;
            return (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => onSelect?.(d.cell_index, d.line, d.column)}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-surface-variant"
                >
                  <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} />
                  <span className="min-w-0 flex-1">
                    <span className="text-fg">{d.message}</span>
                    <span className="ml-2 whitespace-nowrap text-xs text-fg-faint">
                      célula {d.cell_index + 1}:{d.line + 1} · {d.source}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
