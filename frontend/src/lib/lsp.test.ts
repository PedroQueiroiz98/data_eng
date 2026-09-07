import { afterEach, describe, expect, it, vi } from "vitest";
import { lspComplete, lspDiagnostics, lspHealth } from "@/lib/lsp";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("lib/lsp — resiliência", () => {
  it("completions devolve {ok:false} quando o fetch falha", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    const r = await lspComplete({ cells: ["x"], cellIndex: 0, line: 0, column: 1 });
    expect(r.ok).toBe(false);
    expect(r.items).toEqual([]);
  });

  it("completions devolve {ok:false} em resposta não-200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    const r = await lspComplete({ cells: ["x"], cellIndex: 0, line: 0, column: 1 });
    expect(r.ok).toBe(false);
  });

  it("completions repassa o corpo em caso de sucesso", async () => {
    const body = {
      ok: true,
      engine: "jedi",
      took_ms: 12,
      items: [{ label: "append", insert_text: "append", kind: "method", detail: "", documentation: "" }],
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
    vi.stubGlobal("fetch", fetchMock);
    const r = await lspComplete({ cells: ["clientes=[]", "clientes."], cellIndex: 1, line: 0, column: 9 });
    expect(r.ok).toBe(true);
    expect(r.items[0]!.label).toBe("append");
    const [, init] = fetchMock.mock.calls[0]!;
    expect(JSON.parse(init.body)).toMatchObject({ cell_index: 1, line: 0, column: 9 });
  });

  it("diagnostics degrada para lista vazia em erro", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const r = await lspDiagnostics(["x = "]);
    expect(r.ok).toBe(false);
    expect(r.items).toEqual([]);
  });

  it("health devolve ready:false quando o serviço está fora", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const h = await lspHealth();
    expect(h.ready).toBe(false);
  });
});
