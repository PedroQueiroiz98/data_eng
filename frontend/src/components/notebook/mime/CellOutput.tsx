import { useMemo, useState } from "react";
import DOMPurify from "dompurify";
import type { CellOutput as CellOutputData } from "@/lib/notebooks";
import { parseAnsi } from "@/components/notebook/mime/ansi";
import { CopyIconBtn } from "@/components/notebook/mime/CopyIconBtn";
import { DataViewer } from "@/components/workspace/DataViewer";

const DF_MIME = "application/vnd.nbplatform.dataframe+json";

function joinText(v: string | string[] | undefined): string {
  if (!v) return "";
  return Array.isArray(v) ? v.join("") : v;
}

function Ansi({ text }: { text: string }) {
  const spans = useMemo(() => parseAnsi(text), [text]);
  return (
    <>
      {spans.map((s, i) => (
        <span
          key={i}
          style={{ fontWeight: s.bold ? 600 : 400, color: s.color ?? undefined }}
        >
          {s.text}
        </span>
      ))}
    </>
  );
}

function DataOutput({ payload }: { payload: Record<string, unknown> }) {
  const rows = (payload.rows as unknown[][]) ?? [];
  const total = typeof payload.total === "number" ? payload.total : rows.length;
  return (
    <DataViewer
      columns={(payload.columns as string[]) ?? []}
      dtypes={(payload.dtypes as string[]) ?? []}
      rows={rows}
      total={total}
      truncated={Boolean(payload.truncated)}
      embedded
    />
  );
}

function HtmlOutput({ html }: { html: string }) {
  const clean = useMemo(
    () => DOMPurify.sanitize(html, { USE_PROFILES: { html: true } }),
    [html],
  );
  return (
    <div
      className="nbp-html-output max-w-full overflow-x-auto text-sm"
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}

function JsonOutput({ value }: { value: unknown }) {
  const [open, setOpen] = useState(true);
  const text = useMemo(() => JSON.stringify(value, null, 2), [value]);
  return (
    <div className="text-xs">
      <button
        type="button"
        className="mb-1 text-fg-faint hover:text-fg"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "▾" : "▸"} JSON
      </button>
      {open && (
        <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-fg">{text}</pre>
      )}
    </div>
  );
}

function ErrorOutput({ output }: { output: CellOutputData }) {
  const tb = (output.traceback ?? []).join("\n");
  const body = tb || `${output.ename ?? "Error"}: ${output.evalue ?? ""}`;
  return (
    <div className="rounded border border-danger/40 bg-danger/5 p-2">
      <div className="mb-1 flex items-center gap-2 text-xs font-semibold text-danger">
        <span>❌ {output.ename || "Erro de execução"}</span>
        <CopyIconBtn value={body} label="Copiar erro" />
      </div>
      <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs text-fg">
        <Ansi text={body} />
      </pre>
    </div>
  );
}

function Bundle({ data }: { data: Record<string, unknown> }) {
  if (data[DF_MIME]) {
    return <DataOutput payload={data[DF_MIME] as Record<string, unknown>} />;
  }
  const html = data["text/html"];
  if (typeof html === "string" || Array.isArray(html)) {
    return <HtmlOutput html={joinText(html as string | string[])} />;
  }
  for (const mime of ["image/png", "image/jpeg"] as const) {
    const val = data[mime];
    if (typeof val === "string") {
      return (
        <img
          alt="output"
          className="max-w-full"
          src={`data:${mime};base64,${val.replace(/\s/g, "")}`}
        />
      );
    }
  }
  const svg = data["image/svg+xml"];
  if (typeof svg === "string" || Array.isArray(svg)) {
    const clean = DOMPurify.sanitize(joinText(svg as string | string[]));
    return (
      <div
        className="max-w-full overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: clean }}
      />
    );
  }
  if (data["application/json"] !== undefined) {
    return <JsonOutput value={data["application/json"]} />;
  }
  return (
    <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs text-fg">
      <Ansi text={joinText(data["text/plain"] as string | string[])} />
    </pre>
  );
}

export function CellOutput({ output }: { output: CellOutputData }) {
  if (output.output_type === "error") return <ErrorOutput output={output} />;
  if (output.output_type === "stream") {
    const isErr = output.name === "stderr";
    return (
      <pre
        className={`overflow-x-auto whitespace-pre-wrap font-mono text-xs ${
          isErr ? "text-danger" : "text-fg"
        }`}
      >
        <Ansi text={joinText(output.text)} />
      </pre>
    );
  }
  if (output.data) return <Bundle data={output.data as Record<string, unknown>} />;
  return null;
}

export function CellOutputList({ outputs }: { outputs: CellOutputData[] | undefined }) {
  if (!outputs || outputs.length === 0) return null;
  return (
    <div className="space-y-1.5 border-t border-surface-border bg-surface-variant px-3 py-2">
      {outputs.map((out, i) => (
        <CellOutput key={i} output={out} />
      ))}
    </div>
  );
}
