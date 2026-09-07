import { useEffect, useMemo, useRef, useState } from "react";
import { IconButton } from "@/ui/IconButton";
import { useToast } from "@/ui/Toast";
import { DownloadIcon, DuplicateIcon } from "@/ui/icons";

export interface LogLine {
  seq: number;
  level?: string;
  message: string;
}

const LEVELS = ["ALL", "INFO", "WARNING", "ERROR"] as const;

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
  const [level, setLevel] = useState<(typeof LEVELS)[number]>("ALL");
  const [query, setQuery] = useState("");
  const [autoscroll, setAutoscroll] = useState(true);
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
    filtered.map((l) => `${String(l.seq).padStart(4, "0")} ${l.message}`).join("\n");

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value as (typeof LEVELS)[number])}
            className="rounded border border-surface-border bg-surface px-2 py-1 text-xs"
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l === "ALL" ? "Todos os níveis" : l}
              </option>
            ))}
          </select>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Pesquisar"
            className="w-40 rounded border border-surface-border bg-surface px-2 py-1 text-xs"
          />
          <label className="flex items-center gap-1 text-xs text-slate-500">
            <input
              type="checkbox"
              checked={autoscroll}
              onChange={(e) => setAutoscroll(e.target.checked)}
            />
            auto-scroll
          </label>
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
      <div className="max-h-96 overflow-auto rounded-lg border border-slate-800 bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100">
        {filtered.length === 0 && <span className="text-slate-500">sem logs…</span>}
        {filtered.map((l) => (
          <div
            key={l.seq}
            className={
              (l.level ?? "INFO") === "ERROR"
                ? "text-red-400"
                : (l.level ?? "INFO") === "WARNING"
                  ? "text-amber-300"
                  : ""
            }
          >
            <span className="select-none text-slate-500">
              {String(l.seq).padStart(4, "0")}{" "}
            </span>
            {l.message}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
