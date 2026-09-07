import { describe, expect, it } from "vitest";
import { bulkRun, bulkSuccessMessage, summarizeFailures } from "@/lib/bulk";

describe("bulkRun", () => {
  it("conta sucessos e coleta falhas por id", async () => {
    const res = await bulkRun(["1", "2", "3"], async (id) => {
      if (id === "2") throw new Error("job em execução");
      return id;
    });
    expect(res.ok).toBe(2);
    expect(res.failed).toBe(1);
    expect(res.failures).toEqual([{ id: "2", message: "job em execução" }]);
  });

  it("todos ok → sem falhas", async () => {
    const res = await bulkRun(["1", "2"], async () => undefined);
    expect(res).toEqual({ ok: 2, failed: 0, failures: [] });
  });

  it("usa mensagem padrão quando o erro não tem message", async () => {
    const res = await bulkRun(["x"], async () => {
      throw "boom";
    });
    expect(res.failures[0]).toEqual({ id: "x", message: "erro desconhecido" });
  });
});

describe("summarizeFailures", () => {
  it("agrupa por mensagem e resolve os nomes", () => {
    const s = summarizeFailures(
      [
        { id: "a", message: "Notebook em uso" },
        { id: "b", message: "Notebook em uso" },
        { id: "c", message: "Outro erro" },
      ],
      (id) => `nb-${id}`,
    );
    expect(s.total).toBe(3);
    expect(s.groups).toHaveLength(2);
    expect(s.groups[0]).toEqual({
      message: "Notebook em uso",
      names: ["nb-a", "nb-b"],
    });
  });
});

describe("bulkSuccessMessage", () => {
  it("faz plural", () => {
    expect(bulkSuccessMessage(1, "job")).toBe("1 job excluído");
    expect(bulkSuccessMessage(3, "job")).toBe("3 jobs excluídos");
  });
});
