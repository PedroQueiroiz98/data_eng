import { afterEach, describe, expect, it, vi } from "vitest";
import { assistantInline, assistantRun, assistantStream } from "@/lib/assistant";

afterEach(() => vi.restoreAllMocks());

const CTX = { cells: ["x"], active_cell_index: 0 };

describe("lib/assistant — resiliência", () => {
  it("run nunca lança em erro de rede", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const r = await assistantRun({ task: "EXPLAIN", context: CTX });
    expect(r.ok).toBe(false);
    expect(r.text).toBe("");
  });

  it("run degrada em resposta não-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    const r = await assistantRun({ task: "GENERATE", context: CTX });
    expect(r.ok).toBe(false);
  });

  it("inline devolve '' quando abortado", async () => {
    const ac = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_u: string, init: RequestInit) =>
          new Promise((_res, rej) =>
            init.signal?.addEventListener("abort", () =>
              rej(new DOMException("x", "AbortError")),
            ),
          ),
      ),
    );
    const p = assistantInline({ context: CTX }, ac.signal);
    ac.abort();
    expect(await p).toBe("");
  });

  it("stream monta deltas de vários chunks e termina no done", async () => {
    const chunks = [
      'data: {"delta":"he"}\n\n',
      'data: {"delta":"llo"}\n\ndata: {"done":true,"interaction_id":"i1"}\n\n',
    ];
    let i = 0;
    const reader = {
      read: async () =>
        i < chunks.length
          ? { value: new TextEncoder().encode(chunks[i++]), done: false }
          : { value: undefined, done: true },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body: { getReader: () => reader } }),
    );
    const deltas: string[] = [];
    let done: { error: string | null; interaction_id: string | null } | null = null;
    await assistantStream(
      { task: "CHAT", context: CTX },
      { onDelta: (d) => deltas.push(d), onDone: (info) => (done = info) },
    );
    expect(deltas.join("")).toBe("hello");
    expect(done!).toEqual({ error: null, interaction_id: "i1" });
  });

  it("stream nunca lança em erro de rede", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));
    let done: unknown = null;
    await assistantStream(
      { task: "CHAT", context: CTX },
      { onDelta: () => {}, onDone: (i) => (done = i) },
    );
    expect(done).toEqual({ error: "stream falhou", interaction_id: null });
  });
});
