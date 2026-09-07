import type { ReactNode } from "react";
import { summarizeFailures, type BulkOutcome } from "@/lib/bulk";

/** Monta o conteúdo do diálogo de erro para uma exclusão em massa parcial/total. */
export function bulkFailureReport(
  res: BulkOutcome,
  totalRequested: number,
  nounPlural: string,
  nameOf: (id: string) => string,
): { title: string; message: ReactNode } {
  const { groups } = summarizeFailures(res.failures, nameOf);
  return {
    title:
      res.ok === 0
        ? `Nenhum ${nounPlural.replace(/s$/, "")} foi excluído`
        : `${res.failed} de ${totalRequested} ${nounPlural} não foram excluídos`,
    message: (
      <div className="space-y-3">
        {res.ok > 0 && (
          <p className="text-ok">✓ {res.ok} excluído(s) com sucesso.</p>
        )}
        {groups.map((g, i) => (
          <div key={i}>
            <p className="font-medium text-danger">{g.message}</p>
            <ul className="ml-4 mt-0.5 list-disc text-xs text-fg-muted">
              {g.names.slice(0, 8).map((n, j) => (
                <li key={j}>{n}</li>
              ))}
              {g.names.length > 8 && <li>… e mais {g.names.length - 8}</li>}
            </ul>
          </div>
        ))}
      </div>
    ),
  };
}
