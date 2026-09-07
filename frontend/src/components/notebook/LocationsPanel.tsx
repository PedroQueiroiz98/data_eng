import { type LspLocation } from "@/lib/lsp";
import { locationLabel } from "@/lib/lspShared";
import { CloseIcon } from "@/ui/icons";

interface Props {
  title: string;
  locations: LspLocation[];
  onSelect?: (cellIndex: number, line: number, column: number) => void;
  onClose: () => void;
}

export function LocationsPanel({ title, locations, onSelect, onClose }: Props) {
  return (
    <div className="surface mt-3">
      <div className="flex items-center justify-between border-b border-surface-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-fg-faint">
        <span>{title}</span>
        <button type="button" onClick={onClose} className="text-fg-muted hover:text-fg">
          <CloseIcon className="h-4 w-4" />
        </button>
      </div>
      {locations.length === 0 ? (
        <p className="px-3 py-4 text-sm text-fg-faint">Nenhuma referência encontrada.</p>
      ) : (
        <ul className="max-h-64 divide-y divide-surface-border overflow-y-auto text-sm">
          {locations.map((loc, i) => (
            <li key={i}>
              <button
                type="button"
                disabled={loc.external}
                onClick={() => !loc.external && onSelect?.(loc.cell_index, loc.line, loc.column)}
                className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-surface-variant disabled:cursor-default disabled:opacity-70"
              >
                <span className="whitespace-nowrap text-xs text-fg-muted">{locationLabel(loc)}</span>
                <code className="min-w-0 flex-1 truncate font-mono text-xs text-fg">
                  {loc.preview || loc.external_path || loc.name}
                </code>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
