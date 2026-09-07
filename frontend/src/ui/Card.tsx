import type { HTMLAttributes, ReactNode } from "react";

interface Props extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padded?: boolean;
}

export function Card({ children, padded = true, className = "", ...rest }: Props) {
  return (
    <div className={`surface ${padded ? "p-4" : ""} ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  tone?: "default" | "success" | "danger" | "info";
}) {
  const toneClass = {
    default: "text-fg",
    success: "text-ok",
    danger: "text-danger",
    info: "text-primary",
  }[tone];
  return (
    <Card className="flex items-start justify-between">
      <div>
        <div className="text-xs font-medium uppercase tracking-wide text-fg-faint">
          {label}
        </div>
        <div className={`mt-1 text-3xl font-semibold tabular-nums ${toneClass}`}>{value}</div>
        {hint && <div className="mt-0.5 text-xs text-fg-faint">{hint}</div>}
      </div>
      {icon && <div className="text-fg-faint">{icon}</div>}
    </Card>
  );
}
