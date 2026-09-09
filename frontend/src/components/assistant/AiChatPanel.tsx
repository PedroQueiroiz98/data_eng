import { useRef, useState } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { assistantStream } from "@/lib/assistant";
import { notebookAiContext } from "@/lib/assistantContext";
import { useAssistantStore } from "@/store/assistant";
import { Button } from "@/ui";
import { SendIcon, SpinnerIcon } from "@/ui/icons";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

export function AiChatPanel() {
  const available = useAssistantStore((s) => s.available);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  if (!available) {
    return (
      <p className="p-3 text-xs text-fg-faint">
        Nenhum provedor de IA configurado. Configure em{" "}
        <a href="/assistant" className="text-primary hover:underline">
          /assistant
        </a>
        .
      </p>
    );
  }

  const send = async () => {
    const q = input.trim();
    if (!q || streaming) return;
    setInput("");
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "" }]);
    setStreaming(true);
    const ctx = notebookAiContext()?.overview() ?? {
      cells: [""],
      active_cell_index: 0,
    };
    const ac = new AbortController();
    abortRef.current = ac;
    await assistantStream(
      {
        task: "CHAT",
        context: ctx,
        instruction: q,
        messages: history,
      },
      {
        onDelta: (d) =>
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last) next[next.length - 1] = { role: "assistant", content: last.content + d };
            return next;
          }),
        onDone: ({ error }) => {
          setStreaming(false);
          if (error) {
            setMessages((m) => {
              const next = [...m];
              const last = next[next.length - 1];
              if (last) {
                next[next.length - 1] = {
                  role: "assistant",
                  content: (last.content || "") + `\n\n_⚠️ ${error}_`,
                };
              }
              return next;
            });
          }
        },
        signal: ac.signal,
      },
    );
  };

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3 text-sm">
        {messages.length === 0 && (
          <p className="text-fg-faint">Pergunte algo sobre o notebook aberto…</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-fg" : "text-fg-muted"}>
            <span className="mr-1 text-[11px] uppercase text-fg-faint">
              {m.role === "user" ? "você" : "ia"}
            </span>
            {m.role === "assistant" ? (
              <div
                className="nbp-html-output prose-sm max-w-none"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(
                    marked.parse(m.content || "…", { async: false }) as string,
                  ),
                }}
              />
            ) : (
              <span className="whitespace-pre-wrap">{m.content}</span>
            )}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 border-t border-surface-border p-2">
        <input
          value={input}
          placeholder="Mensagem para a IA…"
          className="flex-1 rounded border border-surface-border bg-surface px-2 py-1 text-sm outline-none"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void send()}
        />
        <Button size="sm" onClick={() => void send()} disabled={streaming}>
          {streaming ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <SendIcon className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
