import { useState } from "react";
import { CheckIcon, DuplicateIcon } from "@/ui/icons";

export function CopyIconBtn({ value, label = "Copiar" }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      title={label}
      className="rounded p-0.5 text-fg-faint hover:bg-surface-variant hover:text-fg"
      onClick={async (e) => {
        e.stopPropagation();
        try {
          await navigator.clipboard.writeText(value);
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        } catch {
          /* clipboard bloqueado */
        }
      }}
    >
      {done ? (
        <CheckIcon className="h-3.5 w-3.5 text-ok" />
      ) : (
        <DuplicateIcon className="h-3.5 w-3.5" />
      )}
    </button>
  );
}
