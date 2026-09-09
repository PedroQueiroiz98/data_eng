import { useMemo, useState } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { Button } from "@/ui";
import { copyText } from "@/lib/clipboard";
import type { AssistantTask } from "@/lib/assistant";
import { AI_TASK_LABEL } from "@/components/assistant/providerMeta";
import { SpinnerIcon } from "@/ui/icons";

interface Props {
  task: AssistantTask;
  text: string;
  streaming: boolean;
  error: string | null;
  originalSource: string;
  onInsert: (code: string) => void;
  onInsertBelow: (code: string) => void;
  onReplace: (code: string) => void;
  onReject: () => void;
}

/** Extrai o 1º bloco ```...``` (ou o texto todo se não houver). */
export function extractCode(text: string): string {
  const m = /```(?:[a-zA-Z]+)?\n([\s\S]*?)```/.exec(text);
  return (m?.[1] ?? text).trim();
}

function lineDiff(a: string, b: string): { sign: " " | "+" | "-"; text: string }[] {
  const A = a.split("\n");
  const B = b.split("\n");
  const setA = new Set(A);
  const setB = new Set(B);
  const out: { sign: " " | "+" | "-"; text: string }[] = [];
  for (const l of A) if (!setB.has(l)) out.push({ sign: "-", text: l });
  for (const l of B) out.push({ sign: setA.has(l) ? " " : "+", text: l });
  return out;
}

const DIFF_TASKS: AssistantTask[] = ["FIX", "OPTIMIZE", "DOCSTRING", "CONVERT"];

export function AiResultCard({
  task,
  text,
  streaming,
  error,
  originalSource,
  onInsert,
  onInsertBelow,
  onReplace,
  onReject,
}: Props) {
  const [showDiff, setShowDiff] = useState(false);
  const code = useMemo(() => extractCode(text), [text]);
  const isCodeTask = task !== "EXPLAIN" && task !== "CHAT";
  const html = useMemo(
    () => DOMPurify.sanitize(marked.parse(text || "…", { async: false }) as string),
    [text],
  );

  const significant =
    DIFF_TASKS.includes(task) ||
    (originalSource &&
      lineDiff(originalSource, code).filter((d) => d.sign !== " ").length >
        originalSource.split("\n").length * 0.3);

  return (
    <div className="mt-2 rounded border border-primary/40 bg-primary-container/10">
      <div className="flex items-center gap-2 border-b border-primary/20 px-3 py-1.5 text-xs">
        <span className="font-medium text-primary">✨ {AI_TASK_LABEL[task] ?? task}</span>
        {streaming && <SpinnerIcon className="h-3.5 w-3.5 animate-spin text-fg-muted" />}
        {error && <span className="text-danger">{error}</span>}
        {isCodeTask && significant && (
          <button
            type="button"
            className="ml-auto text-fg-muted hover:text-fg"
            onClick={() => setShowDiff((v) => !v)}
          >
            {showDiff ? "ver código" : "ver diff"}
          </button>
        )}
      </div>

      {isCodeTask && showDiff ? (
        <pre className="max-h-72 overflow-auto p-3 font-mono text-xs leading-5">
          {lineDiff(originalSource, code).map((d, i) => (
            <div
              key={i}
              className={
                d.sign === "+"
                  ? "bg-ok/15 text-ok"
                  : d.sign === "-"
                    ? "bg-danger/15 text-danger"
                    : "text-fg-muted"
              }
            >
              {d.sign} {d.text}
            </div>
          ))}
        </pre>
      ) : isCodeTask ? (
        <pre className="max-h-72 overflow-auto p-3 font-mono text-xs leading-5 text-fg">
          {code || "…"}
        </pre>
      ) : (
        <div
          className="nbp-html-output prose-sm max-w-none px-3 py-2 text-sm"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      )}

      {!streaming && (
        <div className="flex flex-wrap items-center gap-1.5 border-t border-primary/20 px-3 py-1.5">
          {isCodeTask && (
            <>
              <Button size="sm" onClick={() => onInsert(code)}>
                Inserir
              </Button>
              <Button size="sm" variant="outlined" onClick={() => onInsertBelow(code)}>
                Inserir abaixo
              </Button>
              <Button size="sm" variant="outlined" onClick={() => onReplace(code)}>
                {significant ? "Aplicar" : "Substituir"}
              </Button>
            </>
          )}
          <Button
            size="sm"
            variant="text"
            onClick={() => void copyText(isCodeTask ? code : text)}
          >
            Copiar
          </Button>
          <Button size="sm" variant="text" onClick={onReject}>
            Descartar
          </Button>
        </div>
      )}
    </div>
  );
}
