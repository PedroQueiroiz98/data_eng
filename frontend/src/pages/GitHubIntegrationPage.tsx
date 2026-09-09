import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  useConnectGithub,
  useDisconnectGithub,
  useGithubBranches,
  useGithubRepos,
  useGithubStatus,
} from "@/hooks/useGithub";
import { useGitRemoteLink } from "@/hooks/useGit";
import { Button, Card, PageHeader, SelectField, TextField, useConfirm, useToast } from "@/ui";
import { CheckIcon, ConnectIcon, GithubIcon, LogoutIcon } from "@/ui/icons";

const WS = "root"; // Workspace único (`/root`) — mesma convenção de pages/Workspace.tsx
const TOKEN_HELP_URL =
  "https://github.com/settings/tokens/new?scopes=repo&description=nbplatform";

export function GitHubIntegrationPage() {
  const status = useGithubStatus();
  const connect = useConnectGithub();
  const disconnect = useDisconnectGithub();
  const confirm = useConfirm();
  const toast = useToast();
  const [token, setToken] = useState("");

  const connected = !!status.data?.connected;

  const doConnect = () => {
    if (!token.trim()) {
      toast.error("Cole o token antes de conectar.");
      return;
    }
    connect.mutate(token.trim(), {
      onSuccess: (acc) => {
        toast.success(`Conectado como ${acc.username}`);
        setToken("");
      },
      onError: (e) => toast.error((e as Error).message),
    });
  };

  const doDisconnect = async () => {
    if (
      await confirm({
        title: "Desconectar GitHub",
        message:
          "O token salvo será removido. O vínculo de repositório também deixa de funcionar até você reconectar.",
        confirmLabel: "Desconectar",
        danger: true,
      })
    ) {
      disconnect.mutate(undefined, {
        onSuccess: () => toast.success("Conta desconectada."),
        onError: (e) => toast.error((e as Error).message),
      });
    }
  };

  return (
    <div>
      <PageHeader
        title="Integração GitHub"
        subtitle="Conecte sua conta pessoal do GitHub e vincule um repositório ao seu Workspace."
      />

      <div className="mb-4 flex gap-3 rounded-lg border border-surface-border bg-surface-variant/50 p-3 text-sm text-fg-muted">
        <GithubIcon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p>
          O token (PAT) fica cifrado no servidor e nunca é devolvido em texto claro — nem pra
          você, nem nos logs. A conexão é pessoal: cada usuário conecta sua própria conta.
        </p>
      </div>

      <Card>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-faint">
          Conta do GitHub
        </h2>

        {status.isLoading ? (
          <p className="text-sm text-fg-faint">Carregando…</p>
        ) : connected ? (
          <div className="flex items-center gap-3">
            {status.data?.avatar_url && (
              <img
                src={status.data.avatar_url}
                alt={status.data.username ?? "avatar"}
                className="h-12 w-12 rounded-full border border-surface-border"
              />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 text-sm font-medium text-fg">
                <CheckIcon className="h-3.5 w-3.5 text-ok" />
                {status.data?.username}
              </div>
              <div className="truncate text-xs text-fg-muted">{status.data?.email ?? "—"}</div>
            </div>
            <Button
              size="sm"
              variant="outlined"
              icon={<LogoutIcon className="h-4 w-4" />}
              loading={disconnect.isPending}
              onClick={() => void doDisconnect()}
            >
              Desconectar
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3 sm:max-w-md">
            <TextField
              label="Personal Access Token (PAT)"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="ghp_…"
              hint={
                <>
                  Precisa do escopo <span className="font-mono">repo</span>.{" "}
                  <a
                    href={TOKEN_HELP_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary hover:underline"
                  >
                    Como gerar um token →
                  </a>
                </>
              }
            />
            <Button
              icon={<ConnectIcon className="h-4 w-4" />}
              loading={connect.isPending}
              disabled={!token.trim()}
              onClick={doConnect}
            >
              Conectar Conta
            </Button>
          </div>
        )}
      </Card>

      {connected && <RepoLinkCard repoFullName={status.data?.repo_full_name ?? null} />}
    </div>
  );
}

function RepoLinkCard({ repoFullName }: { repoFullName: string | null }) {
  const toast = useToast();
  const repos = useGithubRepos(true);
  const [selectedRepo, setSelectedRepo] = useState("");
  const [branch, setBranch] = useState("");
  const [baseDir, setBaseDir] = useState("");
  const branches = useGithubBranches(selectedRepo || null);
  const link = useGitRemoteLink(WS);

  const selected = repos.data?.find((r) => r.full_name === selectedRepo);

  useEffect(() => {
    if (selected && !branch) setBranch(selected.default_branch);
  }, [selected, branch]);

  const doInit = () => {
    if (!selectedRepo || !branch) {
      toast.error("Escolha o repositório e a branch.");
      return;
    }
    link.mutate(
      { repoFullName: selectedRepo, branch, baseDir },
      {
        onSuccess: (r) => {
          if (r.conflicts.length > 0) {
            toast.error(
              `Trazido com ${r.conflicts.length} conflito(s) — resolva no painel Git do Workspace.`,
            );
          } else {
            toast.success("Repositório inicializado no Workspace.");
          }
        },
        onError: (e) => toast.error((e as Error).message),
      },
    );
  };

  return (
    <Card className="mt-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-faint">
        Repositório
      </h2>

      {repoFullName && (
        <p className="mb-3 text-sm text-fg-muted">
          Vinculado atualmente a <span className="font-mono text-fg">{repoFullName}</span>. Vincular
          outro repositório abaixo troca a origem sincronizada.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField
          label="Repositório"
          value={selectedRepo}
          onChange={(e) => {
            setSelectedRepo(e.target.value);
            setBranch("");
          }}
        >
          <option value="">
            {repos.isLoading ? "Carregando…" : "Selecione um repositório"}
          </option>
          {(repos.data ?? []).map((r) => (
            <option key={r.full_name} value={r.full_name}>
              {r.full_name}
              {r.private ? " (privado)" : ""}
            </option>
          ))}
        </SelectField>

        <SelectField
          label="Branch principal"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          disabled={!selectedRepo}
        >
          {branch && !branches.data?.some((b) => b.name === branch) && (
            <option value={branch}>{branch}</option>
          )}
          {(branches.data ?? []).map((b) => (
            <option key={b.name} value={b.name}>
              {b.name}
            </option>
          ))}
        </SelectField>

        <TextField
          label="Pasta base do Workspace"
          value={baseDir}
          onChange={(e) => setBaseDir(e.target.value)}
          placeholder="(raiz)"
          hint="Vazio = sincroniza a Home inteira."
        />
      </div>

      <Button
        className="mt-3"
        loading={link.isPending}
        disabled={!selectedRepo || !branch}
        onClick={doInit}
      >
        Inicializar Repositório no Workspace
      </Button>
      <p className="mt-2 text-xs text-fg-faint">
        Traz o conteúdo do repositório pro seu Workspace. Se já houver arquivos locais, tenta
        mesclar — conflitos aparecem no{" "}
        <Link to="/workspace" className="text-primary hover:underline">
          painel Git do Workspace
        </Link>
        .
      </p>
    </Card>
  );
}
