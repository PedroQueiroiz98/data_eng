import { useEffect, useState, type ComponentType } from "react";
import { NavLink } from "react-router-dom";
import { Tooltip } from "@/ui/Tooltip";
import {
  CollapseIcon,
  DashboardIcon,
  ExpandIcon,
  HistoryIcon,
  JobsIcon,
  NotebookIcon,
  ScheduleIcon,
  SecretIcon,
  VariableIcon,
  WorkflowIcon,
} from "@/ui/icons";

interface Item {
  label: string;
  to: string;
  Icon: ComponentType<{ className?: string }>;
}

const ITEMS: Item[] = [
  { label: "Dashboard", to: "/dashboard", Icon: DashboardIcon },
  { label: "Notebooks", to: "/notebooks", Icon: NotebookIcon },
  { label: "Workflows", to: "/workflows", Icon: WorkflowIcon },
  { label: "Jobs", to: "/jobs", Icon: JobsIcon },
  { label: "Execuções", to: "/executions", Icon: HistoryIcon },
  { label: "Agendamentos", to: "/schedules", Icon: ScheduleIcon },
  { label: "Variáveis", to: "/variables", Icon: VariableIcon },
  { label: "Secrets", to: "/secrets", Icon: SecretIcon },
];

const STORE_KEY = "nbp.sidebar.collapsed";

interface Props {
  mobileOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ mobileOpen, onClose }: Props) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORE_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  // colapsado só afeta o rail em md+; no drawer mobile é sempre expandido
  const labelCls = collapsed ? "md:hidden" : "";
  const centerCls = collapsed ? "md:justify-center" : "";

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      <nav
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-surface-border
          bg-surface transition-[transform,width] md:static md:z-auto md:translate-x-0
          ${collapsed ? "md:w-16" : "md:w-60"}
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
        aria-label="Navegação principal"
      >
        <div className={`flex h-14 shrink-0 items-center gap-2 border-b border-surface-border px-4 ${centerCls}`}>
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-primary text-sm font-bold text-primary-fg">
            n
          </span>
          <span className={`text-base font-semibold text-fg ${labelCls}`}>nbplatform</span>
        </div>

        <div className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-3">
          {ITEMS.map((item) => (
            <Tooltip key={item.to} label={item.label} side="right">
              <NavLink
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm transition ${centerCls}
                   ${
                     isActive
                       ? "bg-primary-container font-medium text-primary-on-container"
                       : "text-fg-muted hover:bg-surface-variant"
                   }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r bg-primary" />
                    )}
                    <item.Icon className="h-5 w-5 shrink-0" />
                    <span className={`truncate ${labelCls}`}>{item.label}</span>
                  </>
                )}
              </NavLink>
            </Tooltip>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="hidden items-center gap-2 border-t border-surface-border px-4 py-2.5 text-xs
            text-fg-muted hover:bg-surface-variant md:flex"
        >
          {collapsed ? <ExpandIcon className="h-4 w-4" /> : <CollapseIcon className="h-4 w-4" />}
          <span className={labelCls}>Recolher</span>
        </button>
      </nav>
    </>
  );
}
