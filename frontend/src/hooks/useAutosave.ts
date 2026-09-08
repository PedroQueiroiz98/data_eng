import { useEffect, useRef } from "react";

interface Options {
  dirty: boolean;
  enabled: boolean;
  intervalMs: number;
  onSave: () => void | Promise<void>;
}

/** Salva `onSave` após `intervalMs` de inatividade enquanto `dirty && enabled`. */
export function useAutosave({ dirty, enabled, intervalMs, onSave }: Options): void {
  const saving = useRef(false);
  const onSaveRef = useRef(onSave);
  onSaveRef.current = onSave;

  useEffect(() => {
    if (!enabled || !dirty) return;
    const handle = setTimeout(async () => {
      if (saving.current) return;
      saving.current = true;
      try {
        await onSaveRef.current();
      } finally {
        saving.current = false;
      }
    }, Math.max(2000, intervalMs));
    return () => clearTimeout(handle);
  }, [enabled, dirty, intervalMs]);
}
