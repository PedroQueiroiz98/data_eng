import { useEffect, useMemo, useRef, useState } from "react";
import { IconButton } from "@/ui/IconButton";
import { useToast } from "@/ui/Toast";
import { DownloadIcon, DuplicateIcon, MaximizeIcon, MinimizeIcon } from "@/ui/icons";

export interface LogLine {
  seq: number;
  level?: string;
  message: string;
  ts?: string;
}

const LEVELS = [
  { id: "ALL", label: "Todos" },
  { id: "INFO", label: "Info" },
  { id: "WARNING", label: "Warn" },
  { id: "ERROR", label: "Error" },
] as const;
type Level = (typeof LEVELS)[number]["id"];

function clock(ts?: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString();
}

export function LogTerminal({
  lines,
  title = "Logs",
  filename = "logs.txt",
}: {
  lines: LogLine[];
  title?: string;
  filename?: string;
}) {
  const toast = useToast();
  const [level, setLevel] = useState<Level>("ALL");
  const [query, setQuery] = useState("");
  const [autoscroll, setAutoscroll] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return lines.filter(
      (l) =>
        (level === "ALL" || (l.level ?? "INFO") === level) &&
        (!q || l.message.toLowerCase().includes(q)),
    );
  }, [lines, level, query]);

  useEffect(() => {
    if (autoscroll) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [filtered.length, autoscroll]);

  const asText = () =>
    filtered
      .map((l) => `${l.ts ? `[${clock(l.ts)}] ` : ""}${(l.level ?? "INFO").padEnd(5)} ${l.message}`)
      .join("\n");

  const counts = useMemo(() => {
    let warn = 0;
    let err = 0;
    for (const l of lines) {
      if (l.level === "WARNING") warn++;
      else if (l.level === "ERROR") err++;
    }
    return { warn, err };
  }, [lines]);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-fg">{title}</h2>
        <div className="flex items-center gap-0.5 rounded-md border border-surface-border p-0.5">
          {LEVELS.map((l) => {
            const on = level === l.id;
            const badge =
              l.id === "WARNING" ? counts.warn : l.id === "ERROR" ? counts.err : null;
            return (
              <button
                key={l.id}
                type="button"
                onClick={() => setLevel(l.id)}
                className={`rounded px-2 py-0.5 text-xs transition ${
                  on ? "bg-primary text-primary-fg" : "text-fg-muted hover:bg-surface-variant"
                }`}
              >
                {l.label}
                {badge != null && badge > 0 && <span className="ml-1 opacity-80">{badge}</span>}
              </button>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Pesquisar nos logs"
            className="w-44 rounded border border-surface-border bg-surface px-2 py-1 text-xs
              placeholder:text-fg-faint focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
          <label className="flex items-center gap-1 text-xs text-fg-muted">
            <input
              type="checkbox"
              checked={autoscroll}
              onChange={(e) => setAutoscroll(e.target.checked)}
            />
            auto-scroll
          </label>
          <IconButton
            label={expanded ? "Recolher" : "Expandir"}
            size="sm"
            icon={
              expanded ? (
                <MinimizeIcon className="h-4 w-4" />
              ) : (
                <MaximizeIcon className="h-4 w-4" />
              )
            }
            onClick={() => setExpanded((v) => !v)}
          />
          <IconButton
            label="Copiar logs"
            size="sm"
            icon={<DuplicateIcon className="h-4 w-4" />}
            onClick={() => {
              void navigator.clipboard?.writeText(asText());
              toast.success("Logs copiados");
            }}
          />
          <IconButton
            label="Baixar logs"
            size="sm"
            icon={<DownloadIcon className="h-4 w-4" />}
            onClick={() => {
              const blob = new Blob([asText()], { type: "text/plain" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = filename;
              a.click();
              URL.revokeObjectURL(url);
            }}
          />
        </div>
      </div>
      <div
        className={`overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-100 ${
          expanded ? "max-h-[75vh]" : "max-h-96"
        }`}
      >
        {filtered.length === 0 && <span className="text-zinc-500">sem logs…</span>}
        {filtered.map((l) => {
          const lvl = l.level ?? "INFO";
          return (
            <div
              key={l.seq}
              className={
                lvl === "ERROR"
                  ? "text-red-400"
                  : lvl === "WARNING"
                    ? "text-amber-300"
                    : ""
              }
            >
              <span className="select-none text-zinc-500">
                {l.ts ? `[${clock(l.ts)}] ` : `${String(l.seq).padStart(4, "0")} `}
              </span>
              {l.message}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
