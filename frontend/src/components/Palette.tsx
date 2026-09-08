import { useEffect, useMemo, useRef, useState } from "react";

export interface PaletteItem {
  id: string;
  label: string;
  sublabel?: string;
}

interface Props {
  open: boolean;
  placeholder: string;
  items: PaletteItem[];
  onPick: (id: string) => void;
  onClose: () => void;
}

const fuzzy = (q: string, text: string): boolean => {
  const t = text.toLowerCase();
  let i = 0;
  for (const ch of q.toLowerCase()) {
    i = t.indexOf(ch, i);
    if (i < 0) return false;
    i += 1;
  }
  return true;
};

export function Palette({ open, placeholder, items, onPick, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim();
    if (!q) return items.slice(0, 50);
    return items
      .filter((it) => fuzzy(q, `${it.label} ${it.sublabel ?? ""}`))
      .slice(0, 50);
  }, [items, query]);

  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, filtered.length - 1)));
  }, [filtered.length]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-start justify-center bg-slate-900/40 pt-24"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-xl overflow-hidden rounded-lg border border-surface-border bg-surface shadow-e4">
        <input
          ref={inputRef}
          value={query}
          placeholder={placeholder}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, filtered.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              const it = filtered[active];
              if (it) {
                onPick(it.id);
                onClose();
              }
            } else if (e.key === "Escape") {
              onClose();
            }
          }}
          className="w-full border-b border-surface-border bg-transparent px-4 py-3 text-sm outline-none"
        />
        <div className="max-h-80 overflow-auto py-1">
          {filtered.length === 0 && (
            <p className="px-4 py-3 text-sm text-fg-faint">Nada encontrado.</p>
          )}
          {filtered.map((it, i) => (
            <button
              key={it.id}
              type="button"
              onMouseEnter={() => setActive(i)}
              onClick={() => {
                onPick(it.id);
                onClose();
              }}
              className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm ${
                i === active ? "bg-primary-container text-primary-on-container" : "hover:bg-surface-variant"
              }`}
            >
              <span className="truncate">{it.label}</span>
              {it.sublabel && (
                <span className="shrink-0 text-xs text-fg-faint">{it.sublabel}</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
