import {
  createContext,
  useCallback,
  useContext,
  useMemo,
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

interface AlertOptions {
  title: string;
  message?: ReactNode;
  okLabel?: string;
  danger?: boolean;
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;
type AlertFn = (opts: AlertOptions) => Promise<void>;

interface DialogCtx {
  confirm: ConfirmFn;
  alert: AlertFn;
}

const Ctx = createContext<DialogCtx | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const [alertOpts, setAlertOpts] = useState<AlertOptions | null>(null);
  const resolver = useRef<((v: boolean) => void) | null>(null);
  const alertResolver = useRef<(() => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((o) => {
    setOpts(o);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const alert = useCallback<AlertFn>((o) => {
    setAlertOpts(o);
    return new Promise<void>((resolve) => {
      alertResolver.current = resolve;
    });
  }, []);

  const done = (value: boolean) => {
    resolver.current?.(value);
    resolver.current = null;
    setOpts(null);
  };
  const doneAlert = () => {
    alertResolver.current?.();
    alertResolver.current = null;
    setAlertOpts(null);
  };

  const value = useMemo<DialogCtx>(() => ({ confirm, alert }), [confirm, alert]);

  return (
    <Ctx.Provider value={value}>
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
            <Button variant={opts?.danger ? "danger" : "filled"} onClick={() => done(true)}>
              {opts?.confirmLabel ?? "Confirmar"}
            </Button>
          </>
        }
      >
        <div className="text-sm text-fg-muted">{opts?.message}</div>
      </Dialog>

      <Dialog
        open={alertOpts !== null}
        onClose={doneAlert}
        title={alertOpts?.title ?? ""}
        width="sm"
        footer={
          <Button variant={alertOpts?.danger ? "danger" : "filled"} onClick={doneAlert}>
            {alertOpts?.okLabel ?? "Entendi"}
          </Button>
        }
      >
        <div className="text-sm text-fg-muted">{alertOpts?.message}</div>
      </Dialog>
    </Ctx.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConfirm fora de ConfirmProvider");
  return ctx.confirm;
}

export function useAlert(): AlertFn {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAlert fora de ConfirmProvider");
  return ctx.alert;
}
