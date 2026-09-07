import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import { ThemeToggle } from "@/components/ThemeToggle";
import { IconButton } from "@/ui/IconButton";
import { LogoutIcon, MenuIcon, SettingsIcon } from "@/ui/icons";

function initials(name?: string, email?: string): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/[\s@.]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0]?.toUpperCase() ?? "");
}

export function Header({ onMenu }: { onMenu: () => void }) {
  const { user, logout } = useAuthContext();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-surface-border bg-surface px-4">
      <div className="md:hidden">
        <IconButton label="Menu" icon={<MenuIcon className="h-5 w-5" />} onClick={onMenu} />
      </div>

      <div className="ml-auto flex items-center gap-1" ref={ref}>
        <ThemeToggle />
        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 text-sm hover:bg-surface-variant"
            aria-haspopup="menu"
            aria-expanded={open}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-container text-xs font-semibold text-primary-on-container">
              {initials(user?.name, user?.email)}
            </span>
            <span className="hidden text-fg sm:block">{user?.name ?? user?.email}</span>
          </button>

          {open && (
            <div
              role="menu"
              className="absolute right-0 top-full z-40 mt-2 w-56 overflow-hidden rounded-md
                border border-surface-border bg-surface py-1 shadow-e3 animate-slide-up"
            >
              <div className="border-b border-surface-border px-3 py-2">
                <div className="truncate text-sm font-medium text-fg">
                  {user?.name}
                </div>
                <div className="truncate text-xs text-fg-muted">{user?.email}</div>
                <div className="mt-0.5 text-[11px] uppercase tracking-wide text-fg-faint">
                  {user?.role}
                </div>
              </div>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  navigate("/settings");
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-fg hover:bg-surface-variant"
              >
                <SettingsIcon className="h-4 w-4 text-fg-faint" />
                Configuração
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  logout();
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger hover:bg-danger/10"
              >
                <LogoutIcon className="h-4 w-4" />
                Sair
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
