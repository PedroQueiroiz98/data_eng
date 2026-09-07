import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { SpinnerIcon } from "@/ui/icons";

type Variant = "filled" | "tonal" | "outlined" | "text" | "danger";
type Size = "sm" | "md";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
  fullWidth?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  filled: "bg-primary text-primary-fg hover:bg-primary-hover shadow-e1 disabled:shadow-none",
  tonal: "bg-primary-container text-primary-on-container hover:brightness-95",
  outlined: "border border-surface-border bg-surface text-slate-700 hover:bg-surface-variant",
  text: "text-primary hover:bg-primary-container/50",
  danger: "bg-red-600 text-white hover:bg-red-700 shadow-e1",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "filled", size = "md", loading, icon, fullWidth, className = "", children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center rounded-md font-medium transition
        disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2
        focus-visible:ring-primary/40 ${VARIANTS[variant]} ${SIZES[size]} ${
        fullWidth ? "w-full" : ""
      } ${className}`}
      {...rest}
    >
      {loading ? (
        <SpinnerIcon className="h-4 w-4 animate-spin" aria-hidden />
      ) : (
        icon
      )}
      {children}
    </button>
  );
});
