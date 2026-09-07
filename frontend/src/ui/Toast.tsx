import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { CheckIcon, CloseIcon, FailIcon, InfoIcon } from "@/ui/icons";

type ToastKind = "success" | "error" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastCtx {
  show: (message: string, kind?: ToastKind) => void;
  success: (m: string) => void;
  error: (m: string) => void;
}

const Ctx = createContext<ToastCtx | null>(null);

const KIND = {
  success: { cls: "border-ok/30 bg-ok/10 text-fg", Icon: CheckIcon },
  error: { cls: "border-danger/30 bg-danger/10 text-fg", Icon: FailIcon },
  info: { cls: "border-surface-border bg-surface text-fg", Icon: InfoIcon },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setItems((xs) => xs.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (message: string, kind: ToastKind = "info") => {
      const id = Date.now() + Math.random();
      setItems((xs) => [...xs, { id, kind, message }]);
      setTimeout(() => remove(id), kind === "error" ? 6000 : 3500);
    },
    [remove],
  );

  const value = useMemo<ToastCtx>(
    () => ({
      show,
      success: (m) => show(m, "success"),
      error: (m) => show(m, "error"),
    }),
    [show],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4">
        {items.map((t) => {
          const { cls, Icon } = KIND[t.kind];
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start gap-2 rounded-md border px-3 py-2
                text-sm shadow-e3 animate-slide-up ${cls}`}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="flex-1">{t.message}</span>
              <button type="button" onClick={() => remove(t.id)} aria-label="Fechar">
                <CloseIcon className="h-4 w-4 opacity-60 hover:opacity-100" />
              </button>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast fora de ToastProvider");
  return ctx;
}
