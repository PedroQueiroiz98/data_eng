import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export interface ContextMenuAction {
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}

export type ContextMenuEntry = ContextMenuAction | "separator";

interface MenuState {
  x: number;
  y: number;
  entries: ContextMenuEntry[];
}

/**
 * Menu de clique-direito posicionado no cursor. Fecha em click-outside / Esc /
 * scroll / resize. Uso:
 *   const { open, menu } = useContextMenu();
 *   <div onContextMenu={(e) => open(e, [...entries])} /> ... {menu}
 */
export function useContextMenu(): {
  open: (e: React.MouseEvent, entries: ContextMenuEntry[]) => void;
  close: () => void;
  menu: ReactNode;
} {
  const [state, setState] = useState<MenuState | null>(null);

  const open = useCallback(
    (e: React.MouseEvent, entries: ContextMenuEntry[]) => {
      e.preventDefault();
      e.stopPropagation();
      setState({ x: e.clientX, y: e.clientY, entries });
    },
    [],
  );
  const close = useCallback(() => setState(null), []);

  const menu = state ? (
    <ContextMenuView state={state} onClose={close} />
  ) : null;

  return { open, close, menu };
}

function ContextMenuView({
  state,
  onClose,
}: {
  state: MenuState;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: state.x, y: state.y });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { offsetWidth: w, offsetHeight: h } = el;
    const x = Math.min(state.x, window.innerWidth - w - 8);
    const y = Math.min(state.y, window.innerHeight - h - 8);
    setPos({ x: Math.max(8, x), y: Math.max(8, y) });
  }, [state.x, state.y]);

  // Dismiss ao interagir FORA do menu. O listener é registrado em fase de
  // captura no `window`, portanto precisa checar `ref.contains(target)` — sem
  // isso, o `mousedown` sobre um item do menu fecha o menu ANTES do `click`
  // disparar e a ação nunca roda. O attach é adiado um tick para que o mesmo
  // gesto que abriu o menu (clique com o botão direito) não o feche de imediato.
  useEffect(() => {
    let armed = false;
    const arm = window.setTimeout(() => {
      armed = true;
    }, 0);

    const isInside = (target: EventTarget | null): boolean =>
      target instanceof Node && !!ref.current?.contains(target);

    const onPointer = (e: Event) => {
      if (!armed) return;
      if (isInside(e.target)) return;
      onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onViewportChange = (e: Event) => {
      // scroll dentro do próprio menu não deve fechá-lo
      if (e.type === "scroll" && isInside(e.target)) return;
      onClose();
    };

    window.addEventListener("mousedown", onPointer, true);
    window.addEventListener("touchstart", onPointer, true);
    window.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("scroll", onViewportChange, true);
    return () => {
      window.clearTimeout(arm);
      window.removeEventListener("mousedown", onPointer, true);
      window.removeEventListener("touchstart", onPointer, true);
      window.removeEventListener("keydown", onKey, true);
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      role="menu"
      style={{ left: pos.x, top: pos.y }}
      className="fixed z-[60] min-w-48 overflow-hidden rounded-md border border-surface-border
        bg-surface py-1 shadow-e3 animate-slide-up"
      onMouseDown={(e) => e.stopPropagation()}
      onContextMenu={(e) => e.preventDefault()}
    >
      {state.entries.map((entry, i) =>
        entry === "separator" ? (
          <div key={i} className="my-1 border-t border-surface-border" />
        ) : (
          <button
            key={i}
            type="button"
            role="menuitem"
            disabled={entry.disabled}
            onClick={() => {
              onClose();
              entry.onClick();
            }}
            className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm
              disabled:opacity-40 ${
                entry.danger
                  ? "text-danger hover:bg-danger/10"
                  : "text-fg hover:bg-surface-variant"
              }`}
          >
            {entry.icon && (
              <span className="text-fg-faint">{entry.icon}</span>
            )}
            {entry.label}
          </button>
        ),
      )}
    </div>
  );
}
