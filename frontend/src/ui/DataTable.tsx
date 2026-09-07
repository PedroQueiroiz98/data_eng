import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
  /** habilita seleção múltipla (checkbox por linha + "selecionar tudo") */
  selectable?: boolean;
  /** barra de ações em massa, exibida quando há linhas selecionadas */
  bulkActions?: (selectedIds: string[], clear: () => void) => ReactNode;
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
  selectable = false,
  bulkActions,
}: Props<T>) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const headCbRef = useRef<HTMLInputElement>(null);

  const allKeys = useMemo(
    () => new Set((rows ?? []).map(rowKey)),
    [rows, rowKey],
  );

  // remove das seleções ids que sumiram (ex.: após exclusão)
  useEffect(() => {
    setSelected((prev) => {
      const next = new Set([...prev].filter((id) => allKeys.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [allKeys]);

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

  const filteredKeys = useMemo(() => filtered.map(rowKey), [filtered, rowKey]);
  const allFilteredSelected =
    filteredKeys.length > 0 && filteredKeys.every((k) => selected.has(k));
  const someSelected = filteredKeys.some((k) => selected.has(k));

  useEffect(() => {
    if (headCbRef.current) {
      headCbRef.current.indeterminate = someSelected && !allFilteredSelected;
    }
  }, [someSelected, allFilteredSelected]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);
  const colCount = columns.length + (selectable ? 1 : 0);

  const clear = () => setSelected(new Set());
  const toggleOne = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const toggleAll = () =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) filteredKeys.forEach((k) => next.delete(k));
      else filteredKeys.forEach((k) => next.add(k));
      return next;
    });

  if (loading) {
    return (
      <div className="space-y-3">
        {searchPlaceholder && <Skel />}
        <SkeletonRows cols={colCount} />
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

  const selectedIds = [...selected].filter((id) => allKeys.has(id));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {searchPlaceholder && (
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
            placeholder={searchPlaceholder}
            className="w-full max-w-xs rounded-md border border-surface-border bg-surface px-3 py-2
              text-sm placeholder:text-fg-faint focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        )}
        {selectable && bulkActions && selectedIds.length > 0 && (
          <div className="ml-auto flex items-center gap-2 rounded-md border border-surface-border bg-surface-variant px-3 py-1.5 text-sm">
            <span className="text-fg-muted">{selectedIds.length} selecionado(s)</span>
            {bulkActions(selectedIds, clear)}
            <button
              type="button"
              onClick={clear}
              className="text-xs text-fg-muted hover:text-fg"
            >
              limpar
            </button>
          </div>
        )}
      </div>

      <div className="surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-variant text-left text-xs font-semibold uppercase tracking-wide text-fg-muted">
              {selectable && (
                <th className="w-10 px-4 py-2.5">
                  <input
                    ref={headCbRef}
                    type="checkbox"
                    checked={allFilteredSelected}
                    onChange={toggleAll}
                    aria-label="Selecionar todos"
                  />
                </th>
              )}
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
            {pageRows.map((row) => {
              const key = rowKey(row);
              const isSel = selected.has(key);
              return (
                <tr
                  key={key}
                  onClick={() => onRowClick?.(row)}
                  className={`${onRowClick ? "row-link" : ""} ${isSel ? "bg-primary/5" : ""}`}
                >
                  {selectable && (
                    <td className="w-10 px-4 py-2.5 align-middle">
                      <input
                        type="checkbox"
                        checked={isSel}
                        onClick={(e) => e.stopPropagation()}
                        onChange={() => toggleOne(key)}
                        aria-label="Selecionar linha"
                      />
                    </td>
                  )}
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
              );
            })}
            {pageRows.length === 0 && (
              <tr>
                <td colSpan={colCount} className="px-4 py-8 text-center text-fg-faint">
                  Nenhum resultado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-end gap-2 text-xs text-fg-muted">
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
  return <div className="h-9 w-full max-w-xs animate-pulse rounded-md bg-fg/10" />;
}
