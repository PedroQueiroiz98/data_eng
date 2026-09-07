import { NavLink } from "react-router-dom";

interface Item {
  label: string;
  to: string;
}

interface Group {
  heading: string | null;
  items: Item[];
}

const GROUPS: Group[] = [
  { heading: null, items: [{ label: "Dashboard", to: "/dashboard" }] },
  {
    heading: "Workspace",
    items: [
      { label: "Notebooks", to: "/notebooks" },
      { label: "Workflows", to: "/workflows" },
    ],
  },
  {
    heading: "Operations",
    items: [
      { label: "Jobs", to: "/jobs" },
      { label: "Executions", to: "/executions" },
      { label: "Schedules", to: "/schedules" },
    ],
  },
  {
    heading: "Administration",
    items: [
      { label: "Variables", to: "/variables" },
      { label: "Secrets", to: "/secrets" },
    ],
  },
];

export function Sidebar() {
  return (
    <nav className="w-56 shrink-0 border-r border-slate-200 bg-slate-50 p-4 text-sm">
      <div className="mb-6 px-2 text-base font-semibold text-slate-800">nbplatform</div>
      {GROUPS.map((group) => (
        <div key={group.heading ?? "root"} className="mb-5">
          {group.heading && (
            <div className="mb-1 px-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              {group.heading}
            </div>
          )}
          {group.items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded px-2 py-1.5 ${
                  isActive
                    ? "bg-slate-200 font-medium text-slate-900"
                    : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}
