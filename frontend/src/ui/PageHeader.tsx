import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { BackIcon } from "@/ui/icons";

interface Crumb {
  label: string;
  to?: string;
}

interface Props {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label?: string };
  breadcrumbs?: Crumb[];
}

export function PageHeader({ title, subtitle, actions, back, breadcrumbs }: Props) {
  return (
    <div className="mb-5">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="mb-1 flex items-center gap-1 text-xs text-slate-400">
          {breadcrumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span>/</span>}
              {c.to ? (
                <Link to={c.to} className="hover:text-slate-600">
                  {c.label}
                </Link>
              ) : (
                <span className="text-slate-500">{c.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {back && (
          <Link
            to={back.to}
            className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"
          >
            <BackIcon className="h-4 w-4" />
            {back.label ?? "Voltar"}
          </Link>
        )}
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold text-slate-900">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
        </div>
        {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
