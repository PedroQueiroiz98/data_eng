import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { openWorkspaceSocket, type FsBatchEvent, type FsChange } from "@/lib/ws";
import { useWorkspaceStore } from "@/store/workspace";

/**
 * Assina o canal `/ws/workspace` e mantém o estado do File Explorer / editores
 * sincronizado com o filesystem real em tempo real — sem F5.
 *
 * Estratégia: invalida a árvore em cache (react-query refaz UM fetch) e, para
 * deletes, limpa o estado órfão de abas/expansão. Cada mudança também vira um
 * CustomEvent `nbp:fs-change` que o editor de notebook escuta.
 */
export function useWorkspaceEvents(): void {
  const qc = useQueryClient();

  useEffect(() => {
    const forgetUnder = useWorkspaceStore.getState().forgetUnder;

    const applyChange = (c: FsChange): void => {
      window.dispatchEvent(
        new CustomEvent("nbp:fs-change", { detail: { op: c.op, path: c.path } }),
      );
      if (c.op === "deleted") forgetUnder(c.path);
    };

    const onBatch = (e: FsBatchEvent): void => {
      for (const c of e.changes) applyChange(c);
      void qc.invalidateQueries({ queryKey: ["workspace", "tree"] });
      // conteúdos de arquivos alterados externamente também precisam refazer fetch
      const updated = e.changes.filter((c) => c.op !== "created" && !c.is_dir);
      for (const c of updated) {
        void qc.invalidateQueries({ queryKey: ["workspace", "file", c.path] });
      }
    };

    const stop = openWorkspaceSocket({
      onBatch,
      onSnapshot: (s) => {
        qc.setQueryData(["workspace", "tree", ""], s.tree);
      },
    });
    return stop;
  }, [qc]);
}
