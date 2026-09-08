import { useEffect, type ReactNode } from "react";
import { IconButton } from "@/ui/IconButton";
import { CloseIcon } from "@/ui/icons";

interface Props {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: "md" | "lg" | "xl";
}

const W = { md: "max-w-md", lg: "max-w-xl", xl: "max-w-2xl" };

/** Painel lateral (à direita). Mesmo comportamento do `Dialog`, ancoragem diferente. */
export function Drawer({ open, onClose, title, children, footer, width = "lg" }: Props) {
  useEffect(() => {
    if (!open) return;
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 animate-fade-in"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={`flex h-full w-full ${W[width]} flex-col bg-surface shadow-e4 animate-slide-in-right`}
      >
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-3">
          <h2 className="text-base font-semibold text-fg">{title}</h2>
          <IconButton
            label="Fechar"
            size="sm"
            icon={<CloseIcon className="h-4 w-4" />}
            onClick={onClose}
          />
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-surface-border px-5 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
