import { useId, useState, type ReactNode } from "react";

interface Props {
  label: string;
  children: ReactNode;
  side?: "top" | "bottom" | "right";
}

const POS = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-1.5",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-1.5",
  right: "left-full top-1/2 -translate-y-1/2 ml-2",
};

export function Tooltip({ label, children, side = "top" }: Props) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined}>{children}</span>
      {open && (
        <span
          role="tooltip"
          id={id}
          className={`pointer-events-none absolute z-50 whitespace-nowrap rounded bg-fg px-2
            py-1 text-xs font-medium text-surface shadow-e2 animate-fade-in ${POS[side]}`}
        >
          {label}
        </span>
      )}
    </span>
  );
}
