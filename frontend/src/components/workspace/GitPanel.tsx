import { useMemo, useState } from "react";
import {
  useGitBranches,
  useGitCheckout,
  useGitCommit,
  useGitCreateBranch,
  useGitDiff,
  useGitDiscard,
  useGitInit,
  useGitLog,
  useGitStatus,
} from "@/hooks/useGit";
import { Button, useConfirm, useToast } from "@/ui";
import { BranchIcon, GitCommitIcon } from "@/ui/icons";

const codeFor = (c: { index: string; worktree: string }): string => {
  if (c.index === "?" ) return "A";
  if (c.worktree === "D" || c.index === "D") return "D";
  if (c.index === "A") return "A";
  return "M";
};

function DiffView({ text }: { text: string }) {
  const lines = useMemo(() => text.split("\n"), [text]);
  return (
    <pre className="max-h-64 overflow-auto rounded border border-surface-border bg-surface-variant p-2 font-mono text-[11px] leading-relaxed">
      {lines.map((l, i) => {
        const cls =
          l.startsWith("+") && !l.startsWith("+++")
            ? "text-ok"
            : l.startsWith("-") && !l.startsWith("---")
              ? "text-danger"
              : l.startsWith("@@")
                ? "text-info"
                : "text-fg-muted";
        return (
          <div key={i} className={cls}>
            {l || " "}
          </div>
        );
      })}
    </pre>
  );
}

export function GitPanel({ workspaceId }: { workspaceId: string }) {
  const toast = useToast();
  const confirm = useConfirm();
  const status = useGitStatus(workspaceId);
  const branches = useGitBranches(workspaceId, !!status.data?.initialized);
  const log = useGitLog(workspaceId, !!status.data?.initialized);
  const init = useGitInit(workspaceId);
  const commit = useGitCommit(workspaceId);
  const createBranch = useGitCreateBranch(workspaceId);
  const checkout = useGitCheckout(workspaceId);
  const discard = useGitDiscard(workspaceId);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("");
  const [diffPath, setDiffPath] = useState<string | undefined>();
  const diff = useGitDiff(workspaceId, diffPath, diffPath !== undefined);

  if (status.isLoading) {
    return <p className="p-3 text-xs text-fg-faint">Carregando estado do Git…</p>;
  }
  if (!status.data?.initialized) {
    return (
      <div className="flex flex-col items-start gap-2 p-3 text-xs text-fg-muted">
        <p>Este Workspace ainda não tem um repositório Git.</p>
        <Button
          size="sm"
          loading={init.isPending}
          onClick={() =>
            init.mutate(undefined, {
              onError: (e) => toast.error((e as Error).message),
            })
          }
        >
          Inicializar repositório
        </Button>
      </div>
    );
  }

  const st = status.data;
  const changes = st.changes.filter((c) => !c.path.startsWith(".git/"));
  const toggle = (p: string) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(p) ? n.delete(p) : n.add(p);
      return n;
    });

  const doCommit = () => {
    const paths = [...selected];
    if (!message.trim()) {
      toast.error("Informe uma mensagem de commit.");
      return;
    }
    commit.mutate(
      { message: message.trim(), paths },
      {
        onSuccess: (r) => {
          toast.success(`Commit ${r.sha.slice(0, 7)}`);
          setMessage("");
          setSelected(new Set());
        },
        onError: (e) => toast.error((e as Error).message),
      },
    );
  };

  return (
    <div className="flex h-full min-h-0 gap-3 p-2 text-xs">
      <div className="flex w-72 shrink-0 flex-col gap-2">
        <div className="flex items-center gap-1">
          <BranchIcon className="h-3.5 w-3.5 text-fg-faint" />
          <select
            value={st.branch ?? ""}
            onChange={(e) =>
              checkout.mutate(e.target.value, {
                onError: (err) => toast.error((err as Error).message),
              })
            }
            className="min-w-0 flex-1 rounded border border-surface-border bg-surface px-1 py-0.5"
          >
            {(branches.data?.branches ?? [st.branch ?? "main"]).map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          <button
            type="button"
            title="Nova branch"
            className="rounded px-1 text-fg-faint hover:bg-surface-variant"
            onClick={async () => {
              const name = window.prompt("Nome da nova branch");
              if (name)
                createBranch.mutate(name, {
                  onError: (e) => toast.error((e as Error).message),
                });
            }}
          >
            +
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded border border-surface-border">
          {changes.length === 0 ? (
            <p className="p-2 text-fg-faint">Nenhuma alteração.</p>
          ) : (
            changes.map((c) => (
              <div
                key={c.path}
                className={`flex items-center gap-1.5 px-2 py-1 hover:bg-surface-variant ${
                  diffPath === c.path ? "bg-surface-variant" : ""
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(c.path)}
                  onChange={() => toggle(c.path)}
                />
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                  onClick={() => setDiffPath(c.path)}
                >
                  <span
                    className={`w-3 font-mono ${
                      codeFor(c) === "D"
                        ? "text-danger"
                        : codeFor(c) === "A"
                          ? "text-ok"
                          : "text-warn"
                    }`}
                  >
                    {codeFor(c)}
                  </span>
                  <span className="truncate">{c.path}</span>
                </button>
                <button
                  type="button"
                  title="Descartar"
                  className="text-fg-faint hover:text-danger"
                  onClick={async () => {
                    if (
                      await confirm({
                        title: "Descartar alterações",
                        message: `Descartar mudanças em "${c.path}"?`,
                        confirmLabel: "Descartar",
                        danger: true,
                      })
                    ) {
                      discard.mutate([c.path], {
                        onError: (e) => toast.error((e as Error).message),
                      });
                    }
                  }}
                >
                  ⨯
                </button>
              </div>
            ))
          )}
        </div>

        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={2}
          placeholder="Mensagem do commit"
          className="rounded border border-surface-border bg-surface px-2 py-1 text-xs outline-none"
        />
        <Button
          size="sm"
          icon={<GitCommitIcon className="h-4 w-4" />}
          loading={commit.isPending}
          disabled={!message.trim()}
          onClick={doCommit}
        >
          Commit {selected.size > 0 ? `(${selected.size})` : "(tudo)"}
        </Button>
      </div>

      <div className="min-w-0 flex-1 overflow-auto">
        {diffPath ? (
          diff.isLoading ? (
            <p className="text-fg-faint">Carregando diff…</p>
          ) : (
            <>
              <div className="mb-1 flex items-center gap-2">
                <span className="font-medium">{diffPath}</span>
                <button
                  type="button"
                  className="text-fg-faint hover:text-fg"
                  onClick={() => setDiffPath(undefined)}
                >
                  fechar
                </button>
              </div>
              <DiffView text={diff.data?.diff || "(sem diferenças textuais)"} />
            </>
          )
        ) : (
          <div>
            <p className="mb-1 font-medium text-fg-muted">Histórico</p>
            {(log.data ?? []).map((c) => (
              <div key={c.sha} className="border-b border-surface-border py-1">
                <span className="font-mono text-fg-faint">{c.sha.slice(0, 7)}</span>{" "}
                {c.subject}
                <span className="ml-2 text-fg-faint">
                  {c.author} · {new Date(c.date).toLocaleString("pt-BR")}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
