import { useMemo, useState } from "react";
import { CopyIconBtn } from "@/components/notebook/mime/CopyIconBtn";
import { DownloadIcon, SearchIcon } from "@/ui/icons";

interface Props {
  columns: string[];
  dtypes?: string[];
  rows: unknown[][];
  total: number | null;
  truncated?: boolean;
  /** compacto, para render dentro de uma célula */
  embedded?: boolean;
  onLoadMore?: () => void;
  loadingMore?: boolean;
}

type Tab = "table" | "chart" | "json";

const cellText = (v: unknown): string =>
  v == null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);

export function DataViewer({
  columns,
  dtypes = [],
  rows,
  total,
  truncated,
  embedded,
  onLoadMore,
  loadingMore,
}: Props) {
  const [tab, setTab] = useState<Tab>("table");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let out = q
      ? rows.filter((r) => r.some((c) => cellText(c).toLowerCase().includes(q)))
      : rows;
    if (sort) {
      const { col, dir } = sort;
      out = [...out].sort((a, b) => {
        const av = a[col];
        const bv = b[col];
        const an = typeof av === "number" ? av : Number(av);
        const bn = typeof bv === "number" ? bv : Number(bv);
        if (!Number.isNaN(an) && !Number.isNaN(bn)) return (an - bn) * dir;
        return cellText(av).localeCompare(cellText(bv)) * dir;
      });
    }
    return out;
  }, [rows, query, sort]);

  const toCsv = (): string => {
    const esc = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    return [
      columns.map(esc).join(","),
      ...filtered.map((r) => r.map((c) => esc(cellText(c))).join(",")),
    ].join("\n");
  };
  const toJson = (): string =>
    JSON.stringify(
      filtered.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]]))),
      null,
      2,
    );

  const download = (text: string, name: string, mime: string) => {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalLabel =
    total == null ? `${rows.length}+ linhas` : `${total.toLocaleString("pt-BR")} linhas`;

  return (
    <div
      className={`flex min-w-0 flex-col rounded border border-surface-border bg-surface ${
        embedded ? "max-h-[420px]" : "h-full"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-surface-border px-2 py-1 text-xs">
        <div className="flex gap-1">
          {(["table", "chart", "json"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded px-2 py-0.5 capitalize ${
                tab === t ? "bg-primary-container text-primary-on-container" : "text-fg-muted hover:bg-surface-variant"
              }`}
            >
              {t === "table" ? "Tabela" : t === "chart" ? "Gráfico" : "JSON"}
            </button>
          ))}
        </div>
        <span className="text-fg-faint">
          {totalLabel} · {columns.length} colunas
        </span>
        <div className="ml-auto flex items-center gap-1">
          <div className="flex items-center gap-1 rounded border border-surface-border px-1.5 py-0.5">
            <SearchIcon className="h-3 w-3 text-fg-faint" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filtrar…"
              className="w-24 bg-transparent text-xs outline-none placeholder:text-fg-faint"
            />
          </div>
          <CopyIconBtn value={toCsv()} label="Copiar tabela (CSV)" />
          <button
            type="button"
            title="Baixar CSV"
            className="rounded p-0.5 text-fg-faint hover:bg-surface-variant hover:text-fg"
            onClick={() => download(toCsv(), "dados.csv", "text/csv")}
          >
            <DownloadIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {tab === "table" && (
          <table className="w-full border-collapse text-xs">
            <thead className="sticky top-0 bg-surface-variant">
              <tr>
                <th className="border-b border-surface-border px-2 py-1 text-right text-fg-faint">#</th>
                {columns.map((c, i) => (
                  <th
                    key={i}
                    className="cursor-pointer select-none border-b border-surface-border px-2 py-1 text-left font-medium"
                    onClick={() =>
                      setSort((s) =>
                        s?.col === i
                          ? { col: i, dir: s.dir === 1 ? -1 : 1 }
                          : { col: i, dir: 1 },
                      )
                    }
                  >
                    {c}
                    {sort?.col === i ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
                    {dtypes[i] ? (
                      <span className="ml-1 font-normal text-fg-faint">{dtypes[i]}</span>
                    ) : null}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, ri) => (
                <tr key={ri} className="hover:bg-surface-variant/50">
                  <td className="border-b border-surface-border px-2 py-1 text-right text-fg-faint">
                    {ri + 1}
                  </td>
                  {r.map((c, ci) => (
                    <td
                      key={ci}
                      className="max-w-[24rem] truncate border-b border-surface-border px-2 py-1"
                      title={cellText(c)}
                    >
                      {cellText(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "json" && (
          <pre className="overflow-x-auto p-2 font-mono text-xs">{toJson()}</pre>
        )}

        {tab === "chart" && <MiniChart columns={columns} rows={filtered} />}
      </div>

      {(truncated || onLoadMore) && (
        <div className="border-t border-surface-border px-2 py-1 text-center text-xs">
          <button
            type="button"
            disabled={loadingMore || !onLoadMore}
            onClick={onLoadMore}
            className="rounded px-2 py-0.5 text-primary hover:bg-surface-variant disabled:opacity-40"
          >
            {loadingMore ? "Carregando…" : "Carregar mais"}
          </button>
        </div>
      )}
    </div>
  );
}

function MiniChart({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  const numCol = useMemo(() => {
    for (let i = 0; i < columns.length; i++) {
      if (rows.slice(0, 20).every((r) => r[i] == null || !Number.isNaN(Number(r[i])))) {
        return i;
      }
    }
    return -1;
  }, [columns, rows]);

  if (numCol < 0) {
    return (
      <p className="p-3 text-xs text-fg-faint">
        Nenhuma coluna numérica para plotar.
      </p>
    );
  }
  const values = rows.slice(0, 60).map((r) => Number(r[numCol]) || 0);
  const max = Math.max(1, ...values.map(Math.abs));
  return (
    <div className="p-3">
      <p className="mb-2 text-xs text-fg-muted">{columns[numCol]} (primeiras {values.length})</p>
      <div className="flex h-40 items-end gap-0.5">
        {values.map((v, i) => (
          <div
            key={i}
            className="min-w-[2px] flex-1 bg-primary/70"
            style={{ height: `${(Math.abs(v) / max) * 100}%` }}
            title={String(v)}
          />
        ))}
      </div>
    </div>
  );
}
