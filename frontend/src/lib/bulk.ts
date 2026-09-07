export interface BulkFailure {
  id: string;
  message: string;
}

export interface BulkOutcome {
  ok: number;
  failed: number;
  failures: BulkFailure[];
}

/** Executa `fn` para vários ids em paralelo, tolerando falhas parciais. */
export async function bulkRun(
  ids: string[],
  fn: (id: string) => Promise<unknown>,
): Promise<BulkOutcome> {
  const results = await Promise.allSettled(ids.map((id) => fn(id)));
  const failures: BulkFailure[] = [];
  let ok = 0;
  results.forEach((r, i) => {
    if (r.status === "fulfilled") ok += 1;
    else {
      const err = r.reason as { message?: string } | undefined;
      failures.push({ id: ids[i]!, message: err?.message || "erro desconhecido" });
    }
  });
  return { ok, failed: failures.length, failures };
}

/** Frase curta para o toast de sucesso. */
export function bulkSuccessMessage(ok: number, noun = "registro"): string {
  return `${ok} ${ok === 1 ? noun : `${noun}s`} excluído${ok === 1 ? "" : "s"}`;
}

/**
 * Agrupa as falhas por motivo e devolve um resumo legível (para o diálogo de erro).
 * `nameOf` converte um id no rótulo exibível (ex.: nome do notebook).
 */
export function summarizeFailures(
  failures: BulkFailure[],
  nameOf: (id: string) => string,
): { total: number; groups: { message: string; names: string[] }[] } {
  const byMessage = new Map<string, string[]>();
  for (const f of failures) {
    const arr = byMessage.get(f.message) ?? [];
    arr.push(nameOf(f.id));
    byMessage.set(f.message, arr);
  }
  return {
    total: failures.length,
    groups: [...byMessage.entries()].map(([message, names]) => ({ message, names })),
  };
}
