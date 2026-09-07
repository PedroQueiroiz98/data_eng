import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Tooltip } from "@/ui/Tooltip";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** obrigatório: acessibilidade + tooltip */
  label: string;
  icon: ReactNode;
  danger?: boolean;
  size?: "sm" | "md";
  tooltipSide?: "top" | "bottom" | "right";
}

export const IconButton = forwardRef<HTMLButtonElement, Props>(function IconButton(
  { label, icon, danger, size = "md", tooltipSide = "top", className = "", ...rest },
  ref,
) {
  const dim = size === "sm" ? "h-8 w-8" : "h-9 w-9";
  return (
    <Tooltip label={label} side={tooltipSide}>
      <button
        ref={ref}
        type="button"
        aria-label={label}
        className={`inline-flex ${dim} items-center justify-center rounded-full text-slate-500
          transition hover:bg-surface-variant hover:text-slate-800 disabled:opacity-40
          focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40
          ${danger ? "hover:bg-red-50 hover:text-red-600" : ""} ${className}`}
        {...rest}
      >
        {icon}
      </button>
    </Tooltip>
  );
});
