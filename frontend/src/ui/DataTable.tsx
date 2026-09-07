import { useMemo, useState, type ReactNode } from "react";
import { ChevronDownIcon } from "@/ui/icons";
import { SkeletonRows } from "@/ui/Skeleton";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  /** valor para ordenação/pesquisa; se ausente a coluna não ordena */
  sortValue?: (row: T) => string | number;
  className?: string;
  align?: "left" | "right";
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  /** habilita a caixa de pesquisa; usa os sortValue das colunas */
  searchPlaceholder?: string;
  empty?: ReactNode;
  pageSize?: number;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  onRowClick,
  searchPlaceholder,
  empty,
  pageSize = 12,
}: Props<T>) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    let out = rows ?? [];
    if (query.trim()) {
      const q = query.toLowerCase();
      out = out.filter((r) =>
        columns.some((c) => {
          const v = c.sortValue?.(r);
          return v != null && String(v).toLowerCase().includes(q);
        }),
      );
    }
    if (sort) {
      const col = columns.find((c) => c.key === sort.key);
      if (col?.sortValue) {
        out = [...out].sort((a, b) => {
          const va = col.sortValue!(a);
          const vb = col.sortValue!(b);
          return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir;
        });
      }
    }
    return out;
  }, [rows, query, sort, columns]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);

  if (loading) {
    return (
      <div className="space-y-3">
        {searchPlaceholder && <Skel />}
        <SkeletonRows cols={columns.length} />
      </div>
    );
  }

  if ((rows?.length ?? 0) === 0 && empty) return <>{empty}</>;

  const toggleSort = (key: string) => {
    setPage(0);
    setSort((s) =>
      s?.key === key ? (s.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 },
    );
  };

  return (
    <div className="space-y-3">
      {searchPlaceholder && (
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
          placeholder={searchPlaceholder}
          className="w-full max-w-xs rounded-md border border-surface-border bg-surface px-3 py-2
            text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
      )}

      <div className="surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-variant text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`px-4 py-2.5 ${c.align === "right" ? "text-right" : ""} ${
                    c.sortValue ? "cursor-pointer select-none" : ""
                  }`}
                  onClick={() => c.sortValue && toggleSort(c.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {c.header}
                    {sort?.key === c.key && (
                      <ChevronDownIcon
                        className={`h-3 w-3 transition ${sort.dir === -1 ? "rotate-180" : ""}`}
                      />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {pageRows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={() => onRowClick?.(row)}
                className={onRowClick ? "row-link" : ""}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`px-4 py-2.5 align-middle ${
                      c.align === "right" ? "text-right" : ""
                    } ${c.className ?? ""}`}
                  >
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-slate-400">
                  Nenhum resultado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-end gap-2 text-xs text-slate-500">
          <span>
            {safePage * pageSize + 1}–{Math.min((safePage + 1) * pageSize, filtered.length)} de{" "}
            {filtered.length}
          </span>
          <button
            type="button"
            disabled={safePage === 0}
            onClick={() => setPage(safePage - 1)}
            className="rounded border border-surface-border px-2 py-1 disabled:opacity-40"
          >
            Anterior
          </button>
          <button
            type="button"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage(safePage + 1)}
            className="rounded border border-surface-border px-2 py-1 disabled:opacity-40"
          >
            Próxima
          </button>
        </div>
      )}
    </div>
  );
}

function Skel() {
  return <div className="h-9 w-full max-w-xs animate-pulse rounded-md bg-slate-200/70" />;
}
