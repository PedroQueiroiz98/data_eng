import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";

interface ConfirmOptions {
  title: string;
  message?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;

const Ctx = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((v: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((o) => {
    setOpts(o);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const done = (value: boolean) => {
    resolver.current?.(value);
    resolver.current = null;
    setOpts(null);
  };

  return (
    <Ctx.Provider value={confirm}>
      {children}
      <Dialog
        open={opts !== null}
        onClose={() => done(false)}
        title={opts?.title ?? ""}
        width="sm"
        footer={
          <>
            <Button variant="text" onClick={() => done(false)}>
              {opts?.cancelLabel ?? "Cancelar"}
            </Button>
            <Button
              variant={opts?.danger ? "danger" : "filled"}
              onClick={() => done(true)}
            >
              {opts?.confirmLabel ?? "Confirmar"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">{opts?.message}</p>
      </Dialog>
    </Ctx.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConfirm fora de ConfirmProvider");
  return ctx;
}
