import { useEffect, useRef, useState, type ReactNode } from "react";
import { IconButton } from "@/ui/IconButton";
import { MoreIcon } from "@/ui/icons";

export interface MenuItem {
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}

interface Props {
  items: MenuItem[];
  label?: string;
}

/** Menu "⋮" para ações secundárias de uma linha/tabela. */
export function ActionMenu({ items, label = "Mais ações" }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative inline-flex">
      <IconButton
        label={label}
        size="sm"
        icon={<MoreIcon className="h-4 w-4" />}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        aria-haspopup="menu"
        aria-expanded={open}
      />
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-40 mt-1 min-w-44 overflow-hidden rounded-md
            border border-surface-border bg-surface py-1 shadow-e3 animate-slide-up"
        >
          {items.map((it, i) => (
            <button
              key={i}
              type="button"
              role="menuitem"
              disabled={it.disabled}
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                it.onClick();
              }}
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm
                disabled:opacity-40 ${
                  it.danger
                    ? "text-danger hover:bg-danger/10"
                    : "text-fg hover:bg-surface-variant"
                }`}
            >
              {it.icon && <span className="text-fg-faint">{it.icon}</span>}
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
