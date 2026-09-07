import type { ReactNode } from "react";

export interface TabDef {
  id: string;
  label: ReactNode;
  badge?: ReactNode;
}

interface Props {
  tabs: TabDef[];
  active: string;
  onChange: (id: string) => void;
}

export function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-surface-border">
      {tabs.map((t) => {
        const on = t.id === active;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={on}
            type="button"
            onClick={() => onChange(t.id)}
            className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition ${
              on
                ? "border-primary font-medium text-fg"
                : "border-transparent text-fg-muted hover:border-surface-border hover:text-fg"
            }`}
          >
            {t.label}
            {t.badge != null && (
              <span className="rounded-full bg-fg/10 px-1.5 text-xs text-fg-muted">{t.badge}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
