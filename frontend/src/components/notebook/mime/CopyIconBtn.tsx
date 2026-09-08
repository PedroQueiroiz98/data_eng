import { useState } from "react";
import { copyText } from "@/lib/clipboard";
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
        if (await copyText(value)) {
          setDone(true);
          setTimeout(() => setDone(false), 1200);
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
