# Plano de evolução — Workspace de Data Engineering

> Base: análise do estado atual (backend + frontend) em 2026-09-07.

## Status de execução

| Fase | Estado | Notas |
|---|---|---|
| **1 — ACL por Workspace** | ✅ backend feito e testado | `workspace_members` (migração `0011`), `WorkspaceRole` (VIEWER/EDITOR/OWNER), `require_workspace_role` em `api/deps.py`, todas as rotas de `routes/workspaces.py` protegidas, endpoints de membros (`GET/PUT/DELETE /workspaces/{id}/members`), backfill de OWNER para donos atuais, proteção de "último OWNER". Corrigido bug latente `MissingGreenlet` em `update_workspace`. Testes: `tests/integration/test_workspace_acl.py`. **Frontend (painel de membros + painel direito) pendente.** |
| **7 — Executar arquivo do Workspace** | ✅ backend feito e testado | `ExecutionService.create_for_workspace`, executor (`worker/execution_manager._start`) passa a materializar `input.ipynb` do arquivo em disco quando `source=WORKSPACE`, injeta `WORKSPACE_ROOT` (liga o `workspace_sdk`). Rota `POST /api/workspaces/{id}/execute` (usa o schema `WorkspaceExecuteRequest` antes órfão). `ExecutionRead` agora expõe `source`/`workspace_id`/`notebook_path`/`source_commit` e aceita `notebook_version_id` nulo. Testes: `tests/integration/test_workspace_execution.py` (e2e Papermill + prova do `workspace_sdk`). **Frontend (botão Run no editor de notebook do workspace) pendente.** |
| 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13 | ⏳ pendente | ver seções abaixo |

Observações desta rodada:
- `docker compose` passou a carregar `compose.yaml` (arquivo genérico adicionado ao
  repo, provavelmente pelo VS Code). Usar `-f docker-compose.yml` explicitamente até
  remover/renomear os arquivos genéricos (`compose.yaml`, `compose.debug.yaml`,
  `Dockerfile`, `.dockerignore`, `requirements.txt` na raiz).
- `.env.example` recebeu credenciais reais do Bitrix numa edição externa — **remover
  antes de commitar** (o arquivo é versionado).
- API do `workspace_sdk`: `write_text(data, rel)` (dado primeiro) — assinatura
  invertida em relação a `read_text(rel)`; fácil de errar. Não alterei (sem
  chamadas hoje); vale padronizar numa fase futura.

---

## 1. Contexto

A aplicação (`nbplatform`) já é uma plataforma de orquestração de notebooks: FastAPI +
SQLAlchemy + Postgres + Redis no backend; React 18 + TypeScript + Vite + Tailwind +
Monaco + React Query + Zustand + React Flow no frontend. Já existem Jobs, Pipelines
(workflows/DAG), execução batch via Papermill (com retry/DLQ/recovery), Scheduler
(APScheduler), Variáveis, Secrets (Fernet), Auditoria, LSP (Jedi via HTTP),
Notificações (Email/Bitrix, recém-endurecidas) e um **Workspace de arquivos em disco**
já scaffoldado (14 endpoints de CRUD de arquivos, árvore, upload/download).

O objetivo é transformar isso num **Workspace estilo Databricks**: file explorer +
repositório Git + editor multi-aba (notebook / Python / SQL / Markdown) + **kernel
Python interativo** + execução de células + integração fim-a-fim Workspace → Repo →
Notebook → Job → Execution → Logs/Artifacts/Notifications.

**Regras deste plano:** incremental, sem recriar nada, sem remover funcionalidade,
sem mocks permanentes, sem secrets no frontend, mantendo *interactive = Kernel* e
*production = Papermill* como caminhos separados (já é a realidade hoje).

---

## 2. Estado atual — o que existe, o que é stub, o que falta

| Área | Hoje | Veredito |
|---|---|---|
| **Workspace (disco)** | `workspaces` + dir UUID com skeleton (`notebooks/ scripts/ data/ …`). `WorkspaceFsService` com guard de path traversal. 14 rotas: tree, read/write file, mkdir, delete, rename, copy, upload, download(zip). | **Pronto e sólido.** Falta: sem entidade *Project*, sem membership/ACL (qualquer usuário logado lê/escreve qualquer workspace), sem drag-drop, sem watch/auto-refresh. |
| **File Explorer (UI)** | `components/workspace/FileTree.tsx` recursivo + `pages/Workspace.tsx` (2 painéis). Todas as ops CRUD ligadas à API. `.ipynb` novo já nasce com célula `parameters`. | **Funcional.** Falta: drag-drop, multi-seleção, busca na árvore, indicador de modificado por linha, painel direito (o enum `rightPanelTab` existe e não é consumido). |
| **Editor de código** | Monaco **já instalado e integrado** (`@monaco-editor/react` + `monaco-editor`, `lib/monaco.ts`, `lib/monacoProviders.ts`). Usado em `FilePreview.tsx` (arquivo único) e por célula em `CellCard.tsx`. Providers Python (completion/hover/signature/definition/auto-import) via REST `/api/lsp/*`. | **Base pronta.** Falta: abas multi-arquivo, Ctrl+S, workers extras do Monaco (só `editor.worker`), gerência de modelos entre abas, format-on-save, breadcrumbs. |
| **Editor de Notebook** | `pages/NotebookEditor.tsx` + `store/notebookEditor.ts` + `components/notebook/CellCard.tsx`: UI real de células (add/dup/move/remove, tipo code/markdown/raw, tag `parameters`, deps pip). Diagnósticos LSP com debounce. | **Editor bom, execução ausente.** Sem botão *run cell*, sem kernel, sem contagem de execução; `CellOutputs.tsx` só renderiza outputs **já gravados** (texto puro — sem HTML/imagem/MIME/widgets). |
| **Notebook `.ipynb` no Workspace** | `FilePreview.tsx` mostra como **JSON cru** no Monaco. | **Gap.** Sem UI de células, sem execução, sem render de output para arquivos do workspace. |
| **Notebook (modelo)** | `Notebook` + `NotebookVersion` (conteúdo nbformat v4 em JSONB no Postgres, versões imutáveis). Executions/Workflows/Jobs referenciam `notebook_version_id`. | **Mundo paralelo ao Workspace.** Nenhuma ponte entre `NotebookVersion.content` e `.ipynb` em disco. |
| **Execução (produção)** | Papermill em subprocess/sandbox (`worker/execution_manager.py`, `papermill_runner.py`), logs → `execution_logs` + Redis pub/sub, retry/DLQ/recovery, mascaramento de secrets no output. | **Pronto.** Já tem colunas `source` (`DB`\|`WORKSPACE`), `workspace_id`, `notebook_path`, `source_commit` — **mas o executor faz `assert notebook_version_id is not None`** ("origem WORKSPACE ainda não suportada"). Seam da "Fase 2" pronto para uso. |
| **Kernel Python interativo** | **Não existe.** `ipykernel` é dep (usado pelo Papermill). Sem `jupyter_client`, sem lifecycle de kernel, sem execução por célula. | **A construir do zero.** |
| **WebSocket / eventos ao vivo** | `ws/events.py` (Redis pub/sub fan-out), rotas `/ws/executions/{id}` e `/ws/jobs/{id}` com snapshot + eventos + resume por `after_seq`. Cliente `lib/ws.ts` com reconnect exponencial e dedupe por `seq`. | **Excelente padrão para reusar** no kernel. |
| **Git** | **Ausente.** Só a tabela `workspace_git_repositories` (metadata: `repo_url`, `default_branch`, `current_branch`, `access_token_ct` nunca escrito), enum `GitProvider`, campo `WorkspaceGitSummary` no schema, e `.gitignore` provisionado no skeleton. Binário `git` **está** no container backend (v2.47.3). | **A construir do zero.** Nenhuma lib, nenhuma chamada, nenhum client GitHub, nenhum storage de token. |
| **`workspace_sdk`** | Pacote `backend/src/workspace_sdk` (`workspace.read_csv/write_json/...`) pronto, espera `$WORKSPACE_ROOT`. | **Não conectado** — o executor nunca injeta `WORKSPACE_ROOT`. |
| **SQL editor** | Só syntax highlight (`.sql` → Monaco `sql`). | **A construir** (conexão/warehouse, run query, result grid, history). |
| **Jobs / Pipelines / Scheduler / Execution UI / Logs / Artifacts / Parameters / Notifications** | Completos e em uso (`WorkflowEditor` com React Flow, `JobDetail` com timeline/DAG/history, `ExecutionDetail` com WS ao vivo + `LogTerminal`, artifacts, params, aba de notificações). | **Preservar.** Só estender para aceitar origem Workspace. |
| **Command palette / autosave / diff viewer / tabs** | Nenhum. | **A construir.** `DiffEditor` vem no pacote Monaco (não importado). |

### Decisão sobre stack de UI

O spec pede Material UI. **O projeto usa Tailwind + kit próprio em `frontend/src/ui/`
(Button, Card, Dialog, DataTable, Tabs, Menu, Toast, …).** Introduzir MUI seria uma
reescrita massiva e viola "não altere grandes partes sem necessidade". **Não
introduzir MUI.** Estender o kit existente. (Idem: manter `lucide-react`, `zustand`,
React Query, React Flow, WebSocket cru — tudo já padronizado.)

---

## 3. Decisões de arquitetura

### 3.1 Notebook: manter DB **e** arquivo, com o Workspace como superfície primária

Não migrar/remover `Notebook`/`NotebookVersion`. Em vez disso, ativar o seam
`ExecutionSource.WORKSPACE` já presente:

- Execução interativa e edição acontecem sobre o **`.ipynb` em disco** no workspace.
- Execução de produção (Job) roda o **arquivo do workspace num commit** via Papermill
  (`source=WORKSPACE`, `workspace_id`, `notebook_path`, `source_commit`).
- `Notebook`/`NotebookVersion` continuam funcionando para jobs legados. Opcional
  (fase tardia): comando de "importar notebook DB → arquivo do workspace".
- Versionamento do workspace = **Git** (não criar uma segunda tabela de versões).

### 3.2 Kernel interativo = novo processo `kernel-worker` + `jupyter_client`

- Novo serviço no compose: `kernel` (`python -m nbplatform.kernel_worker`), mesma
  imagem do backend.
- `KernelSessionManager` mantém `jupyter_client.AsyncKernelManager` por **sessão**
  (chave: `workspace_id + notebook_path + user_id`). 1 kernel por sessão, estado
  preservado entre células. `cwd` do kernel = dir do workspace; `WORKSPACE_ROOT` no
  env (liga o `workspace_sdk`). Variables/Secrets injetados como env (reusar
  `VariableService.resolve` / `SecretService.resolve_all`, mascarar em qualquer eco).
- Fila de execução por sessão (serial) + **Redis pub/sub** reusando exatamente
  `ws/events.py`: canal `kernel:{session_id}`, eventos `cell.started`,
  `cell.stream`, `cell.result` (com MIME bundle), `cell.error`, `cell.finished`,
  `kernel.status` (`starting|idle|busy|dead`).
- Rota `WS /ws/kernels/{session_id}` no mesmo padrão de `/ws/executions/{id}`
  (snapshot + stream + `after_seq`). Cliente: estender `lib/ws.ts` com
  `openKernelSocket`.
- Lifecycle: start/ready/busy/idle/restart/shutdown; **idle-timeout reaper**
  (novo loop, espelhando `worker/recovery.py`); crash do kernel → evento
  `kernel.status=dead` + botão *Restart Kernel* no frontend, notebook salvo intacto.
- Isolamento: kernel roda no sandbox já existente quando `execution_sandbox=docker`;
  em `subprocess` roda como processo filho com env restrito. Um usuário nunca
  recebe a sessão de outro (chave inclui `user_id`; checar ACL do workspace).

### 3.3 Git = wrapper sobre o binário `git` + client GitHub (httpx)

- `GitService` (novo, `backend/src/nbplatform/services/git/`) opera sobre o dir do
  workspace via `asyncio.to_thread(subprocess.run, ["git", ...])`. Sem GitPython
  (menos deps; o binário já está no container).
- `GitHubClient` (httpx) para listar repos / criar PR (fase tardia). Só backend.
- **Token**: PAT ou GitHub App. Cifrado com `SecretCipher` em
  `workspace_git_repositories.access_token_ct` (coluna já existe). Nunca serializado
  para o frontend (o schema `WorkspaceGitSummary` já omite). Credential helper do
  git configurado por processo para não gravar o token em disco.
- Operações: `link` (clona para o dir do workspace ou `git init` + `remote add`),
  `status`, `branch list/create/checkout`, `pull`, `commit`, `push`, `diff`
  (unified + por arquivo). `Execution.source_commit` = `git rev-parse HEAD` no
  momento do run.
- **Job nunca chama Git direto** (regra 38): o orquestrador materializa o worktree
  no commit alvo via `GitService` antes do Papermill.

### 3.4 Concorrência, resiliência, observabilidade (reusar o que existe)

- Locks por arquivo: escrita atômica já existe (`os.replace`). Adicionar
  `ETag`/`If-Match` (mtime/hash) em `PUT /file` para detectar edição concorrente.
- Kernel isolado por sessão; reaper de kernels ociosos; recovery de kernels órfãos
  (espelhar `recover_stale_notifications`, recém-adicionado).
- Logs estruturados + `correlation_id` (padrão já usado). Idempotência de execução
  já existe; estender para "run cell" (id de request por célula).
- Graceful shutdown: `kernel_worker` derruba kernels no `SIGTERM` (espelhar
  `worker/__main__.py`).

---

## 4. Plano por fases

Cada fase é um incremento entregável. "Arquivos" lista os pontos de mudança;
padrões existentes a reusar estão citados.

### Fase 1 — Projetos, ACL e painel direito do Workspace
**Meta:** dar estrutura ao Workspace (Shared/Users/Projects) e permissão por workspace.
- Backend: nova tabela `workspace_members` (`workspace_id`, `user_id`, `role`
  `owner|editor|viewer`); dependency `require_workspace_role(...)` em `api/deps.py`;
  aplicar em todas as rotas de `routes/workspaces.py` (hoje só JWT). Opcional: campo
  `kind` (`shared|user|project`) ou convenção de path no topo da árvore.
- Frontend: `Workspace.tsx` ganha 3ª coluna (painel direito) dirigida pelo
  `rightPanelTab` já no store (`output|git|history`); `Workspaces.tsx` mostra papel
  do usuário e gerencia membros (admin/owner).
- Reusar: `AuditService`, `ConfirmDialog`, `DataTable`.
- **Done-when:** um viewer não consegue `PUT /file`; owner gerencia membros; painel
  direito visível e alternável.

### Fase 2 — Abas multi-arquivo + autosave + estado persistido
**Meta:** editar vários arquivos ao mesmo tempo, sem perder rascunho.
- Frontend: `store/workspace.ts` → `openTabs: TabState[]` (path, kind, dirty, buffer,
  viewState), `activeTabId`, ações `openTab/closeTab/closeOthers/setBuffer`.
  Adicionar `zustand/persist` (chave `nbp.workspace.<id>`). Novo
  `components/workspace/EditorTabs.tsx` (tira de abas com `*`, close, overflow —
  estender `ui/Tabs.tsx`). `FilePreview` passa a receber buffer do tab (não perde no
  switch). Autosave: hook `useAutosave` (debounce ~1.2s) com estados
  *Salvando…/Salvo/Não salvo*; Ctrl/Cmd+S força. `WorkspaceState` (spec §22) =
  o slice persistido; restaurar abas ao reabrir `/workspaces/:id`.
- Backend: `PUT /file` aceita `If-Match` (mtime/hash) → 409 em conflito.
- **Done-when:** abrir 3 arquivos, trocar de aba sem perder edição, recarregar a
  página e as abas voltam; autosave grava; conflito concorrente é detectado.

### Fase 3 — Editor de Notebook do Workspace (células sobre arquivo)
**Meta:** `.ipynb` do workspace abre no editor de células, não em JSON cru.
- Frontend: quando `kind === "notebook"`, `FilePreview` (ou um novo
  `WorkspaceNotebookEditor`) monta o editor de células **reusando
  `store/notebookEditor.ts` + `components/notebook/CellCard.tsx`**, mas com
  persistência via `writeFile` (arquivo) em vez de `POST /versions` (DB). Extrair a
  parte de UI de `NotebookEditor.tsx` para um componente compartilhado
  `NotebookCanvas` usado pelas duas telas.
- Renderers de output ricos: novo `components/notebook/mime/` (text, `text/html`
  saneado, `image/png|jpeg`, `application/json`, traceback ANSI). Usado tanto aqui
  quanto no `NotebookOutputView` (produção).
- **Done-when:** abrir/editar/salvar `.ipynb` do workspace com UI de células; outputs
  gravados renderizam com imagens/HTML.

### Fase 4 — Kernel Python interativo (o item central)
**Meta:** executar células com estado persistente, streaming ao vivo.
- Backend novo pacote `backend/src/nbplatform/kernel/`:
  `session_manager.py` (`AsyncKernelManager` por sessão, `jupyter_client`),
  `protocol.py` (execute_request/iopub → eventos), `reaper.py` (idle timeout).
  Novo entrypoint `backend/src/nbplatform/kernel_worker/__main__.py` (espelha
  `worker/__main__.py`: heartbeat, reaper, graceful shutdown).
- Dep nova: `jupyter_client>=8` no `pyproject.toml` (`ipykernel` já está).
- Rotas `api/routes/kernels.py`: `POST /api/kernels` (abre sessão p/ workspace+path),
  `GET /api/kernels/{id}`, `POST /api/kernels/{id}/execute` (enfileira célula, 202),
  `POST /api/kernels/{id}/interrupt`, `POST /api/kernels/{id}/restart`,
  `DELETE /api/kernels/{id}`. `WS /ws/kernels/{id}` (snapshot + eventos, `after_seq`).
- Reusar: `ws/events.py` (pub/sub), padrão de `routes/ws.py`, injeção de
  Variables/Secrets de `execution_manager._build_env`, mascaramento
  (`core/masking`), sandbox (`worker/sandbox.py`).
- Frontend: `lib/kernels.ts` + `hooks/useKernel.ts` + `openKernelSocket` em
  `lib/ws.ts`. `CellCard.tsx` ganha ▶ Run / ⏹ Stop, contagem `[n]`, spinner busy,
  streaming stdout na célula. `NotebookCanvas` ganha barra: Run all / Restart kernel /
  Interrupt / indicador `Python ● Connected|Busy|Dead`. Crash → banner + Restart.
- Docker: serviço `kernel` no `docker-compose.yml` (mesma imagem, volume
  `workspaces`, sem porta), rebuild de `backend worker scheduler kernel`
  (ver `[[rebuild-all-backend-images]]`).
- **Done-when:** `df = ...` na célula 1, `df.head()` na célula 2 funciona; restart
  limpa estado; kernel morto é detectado e reiniciável; dois usuários = dois kernels.

### Fase 5 — GitHub: conectar repositório + token seguro
**Meta:** ligar um repo GitHub a um workspace, com token só no backend.
- Backend: `services/git/git_service.py` (wrapper `git` CLI, `asyncio.to_thread`),
  `services/git/github_client.py` (httpx). Settings/env: `GITHUB_APP_*` ou aceitar
  PAT do usuário no `POST /connect`. Cifrar em `access_token_ct` via `SecretCipher`.
  Rotas `api/routes/git.py`: `POST /api/workspaces/{id}/git/connect` (PAT + repo_url →
  clone no dir do workspace ou init+remote), `DELETE .../git` (desconectar),
  `GET .../git/status`.
- Segurança: token nunca no response; `git` config `credential.helper` efêmero;
  nunca logar o token (redigir como já se faz no provider Bitrix).
- Frontend: diálogo "Conectar repositório" em `WorkspaceHeader.tsx` (hoje só um
  label). `lib/git.ts` + `hooks/useGit.ts`.
- **Done-when:** conectar um repo privado, arquivos aparecem na árvore, token não
  trafega para o frontend nem aparece em log.

### Fase 6 — Operações Git (branch / status / diff / commit / push / pull)
**Meta:** fluxo de alterações completo dentro do Workspace.
- Backend: expandir `git_service.py` + `api/routes/git.py`:
  `GET .../git/branches`, `POST .../git/branches` (create+checkout),
  `POST .../git/checkout`, `POST .../git/pull`, `POST .../git/commit`
  (paths + message), `POST .../git/push`, `GET .../git/diff?path=` (unified).
- Frontend: painel direito aba **Git** (`rightPanelTab="git"`): branch atual +
  switcher, lista `M/A/D` de mudanças, seleção para commit, campo mensagem,
  botões Pull/Commit/Push. Aba **Diff**: `monaco` `DiffEditor` (já no pacote) via
  `Changes` do arquivo. Indicador `main ● Clean` / `feature ● 3 changes` no header;
  `arquivo.py *` na aba. Command palette (Fase 11) ganha os comandos Git.
- Reusar: `ConfirmDialog` para `discard`. Auditar cada operação (`AuditService`).
- **Done-when:** criar branch, editar, ver diff, commitar, push — e o commit
  aparece no GitHub.

### Fase 7 — Executar arquivo do Workspace (origem WORKSPACE no Papermill)
**Meta:** rodar um `.ipynb` do workspace como Execution de produção.
- Backend: `ExecutionService.create_for_workspace(workspace_id, notebook_path,
  params, commit?)` → cria `Execution` com `source=WORKSPACE`. Remover o
  `assert notebook_version_id` em `worker/execution_manager.py:207`: quando
  `source==WORKSPACE`, materializar `input.ipynb` a partir do arquivo no worktree
  (checkout do `source_commit` se houver repo; senão o arquivo atual), setar
  `WORKSPACE_ROOT` no env (liga `workspace_sdk`), gravar `source_commit =
  git rev-parse HEAD`. Rota `POST /api/workspaces/{id}/execute` (o schema
  `WorkspaceExecuteRequest` já existe e está sem uso).
- Frontend: botão **Run** no editor de notebook do workspace → diálogo de params →
  cria Execution → navega para `/executions/:id` (tela já existe, WS ao vivo já
  funciona).
- **Done-when:** rodar notebook do workspace gera Execution com logs ao vivo,
  `output.ipynb` como artifact e `source_commit` gravado.

### Fase 8 — Jobs e Pipelines com tarefas de Workspace
**Meta:** um Job pode ter tasks apontando para arquivos do workspace (notebook / .py / .sql).
- Backend: adicionar a `workflow_tasks` colunas `source` (`DB|WORKSPACE`),
  `workspace_id`, `notebook_path` (migração aditiva; `notebook_id` continua para
  legado). `JobOrchestrator` / criação de `job_tasks` propaga a origem para a
  Execution (reusa Fase 7). Task type: notebook (Papermill), script `.py`
  (`python arquivo.py` no sandbox), `.sql` (Fase 10).
- Frontend: `WorkflowEditor` (React Flow) — no `TaskNode`, seletor "origem: Notebook
  gerenciado | Arquivo do Workspace" + file picker da árvore do workspace.
- Reusar: toda a orquestração, DAG, dependências, paralelismo, `PipelineGraph`,
  `TaskTimeline`, `RunHistory` — sem mudança.
- **Done-when:** pipeline `extraction.ipynb → transformation.ipynb → load.ipynb`
  (arquivos do workspace) executa como Job, com DAG e history.

### Fase 9 — Scheduler + Parameters + Notifications sobre origem Workspace
**Meta:** nada novo de conceito, só garantir cobertura.
- Backend: `schedules` já dispara Workflow → Job; confirmar que Job de origem
  Workspace agenda igual. Parameters já fluem para Papermill; garantir para
  `source=WORKSPACE`. Notificações (§20) já são desacopladas
  (`_notify_final` → `NotificationService`) — só confere que Job de workspace
  aciona igual (event `JOB_FAILED`). Ver `[[notification-service]]`.
- Frontend: telas de Schedules/params/aba Notificações já servem; sem mudança
  relevante além de rótulos.
- **Done-when:** agendar pipeline de workspace; falha dispara Email/Bitrix;
  `[View Execution]` abre a Execution certa.

### Fase 10 — SQL editor + execução de query
**Meta:** `.sql` vira superfície de primeira classe.
- Backend: `services/sql/` — executor sobre conexões cadastradas (reusar `Secret`
  para credenciais). `POST /api/workspaces/{id}/sql/execute` (query + connection_id
  + limit) → result set paginado. `sql_query_history` (por usuário/workspace).
  Começar com Postgres (asyncpg já é dep); arquitetura aberta para DuckDB/SQL
  Server depois.
- Frontend: `components/workspace/SqlEditor.tsx` — Monaco `sql` + botão Run +
  `ResultGrid` (virtualizado) + history + tempo/erro. Aba no editor quando
  `kind==="text"` e extensão `.sql`.
- Segurança: credenciais só backend; nunca no notebook/response; `LIMIT` forçado.
- **Done-when:** `SELECT * FROM customers LIMIT 100` roda e mostra grid; history
  persiste.

### Fase 11 — Command palette + atalhos + UX de IDE
**Meta:** sensação VS Code.
- Frontend: `components/CommandPalette.tsx` (Ctrl/Cmd+Shift+P e Ctrl/Cmd+K),
  registry de comandos (`lib/commands.ts`): Open File, Create Notebook/Python/SQL,
  Run Cell, Run All, Restart Kernel, Git Pull/Push/Commit, Create Branch, Run Job,
  Open Execution. Painéis redimensionáveis (explorer/editor/direito), breadcrumb de
  path, atalhos de notebook (a/b/dd/m/y estilo Jupyter) em `NotebookCanvas`.
- Sem lib nova obrigatória (pode-se adicionar `cmdk`; ou construir sobre `ui/Menu`).
- **Done-when:** paleta abre, filtra, executa comandos; panes ajustáveis.

### Fase 12 — Resiliência + observabilidade (fechamento)
**Meta:** produção-ready.
- Kernel: reaper de sessões ociosas + recovery de kernels órfãos (espelhar
  `worker/recovery.recover_stale_notifications`), `kernel.status=dead` bem tratado,
  limite de kernels concorrentes (setting), timeout de execução por célula.
- Git: timeout em toda operação, lock por workspace (evitar `git` concorrente),
  tratamento de merge conflict na UI.
- Concorrência de arquivo: `If-Match` em todas as escritas; aviso de "arquivo
  mudou no disco (git pull)".
- Observabilidade: logs estruturados com `correlation_id` em kernel/git/sql;
  métricas (`/metrics` já existe) para sessões de kernel ativas, execuções de
  célula, ops git.
- **Done-when:** matar o `kernel-worker` no meio de uma execução não trava a UI;
  reiniciar recupera; `git` concorrente serializa.

### Fase 13 — Testes end-to-end
Backend (pytest, via `docker compose run` — ver `[[no-local-toolchain]]`):
- workspace fs (já há), ACL por papel, `If-Match` 409.
- kernel: abrir sessão, executar 2 células com estado, restart limpa, kernel crash
  → `dead`, reaper, isolamento entre usuários.
- git: connect (token cifrado, ausente do response/log), branch, commit, push
  (contra um repo git local `file://` nos testes), diff, checkout, pull.
- execução origem WORKSPACE: Papermill roda arquivo, `source_commit` gravado,
  `WORKSPACE_ROOT` disponível ao `workspace_sdk`.
- job/pipeline com task de workspace: success, failure → notificação, retry.
- SQL execute + history.
Frontend (vitest + testing-library):
- abas: abrir/fechar/dirty/restore.
- notebook canvas: add/run/output render.
- kernel socket: eventos → UI (mock WS).
- git panel: status → commit → push (mock API).
- command palette: filtro + dispatch.

---

## 5. Novas dependências (mínimas)

| Onde | Dep | Motivo |
|---|---|---|
| backend | `jupyter_client>=8` | gerência de kernel interativo (`ipykernel` já está) |
| backend | *(nenhuma p/ Git)* | usar binário `git` do container via subprocess |
| backend | *(opcional)* `pygithub`/httpx puro | client GitHub — preferir httpx puro (já é dep) |
| frontend | *(nenhuma obrigatória)* | Monaco/`DiffEditor`, React Flow, WS, zustand/persist já cobrem; `cmdk` é opcional |

Migrações Alembic novas (aditivas, `0011+`): `workspace_members`; `workflow_tasks`
(`source`, `workspace_id`, `notebook_path`); `sql_connections` + `sql_query_history`;
`kernel_sessions` (opcional, se quiser histórico/persistência de sessão).

---

## 6. O que NÃO fazer

- Não introduzir Material UI (o projeto é Tailwind + kit próprio).
- Não remover `Notebook`/`NotebookVersion` nem o fluxo de notebooks gerenciados.
- Não acoplar Job a Git ou a Bitrix/Email diretamente (regra 38 — já respeitado hoje).
- Não usar Papermill para execução interativa nem kernel para produção.
- Não mandar notebook/arquivo grande inteiro para o frontend sem necessidade
  (lazy tree, paginação de result grid, streaming de log — padrões já existentes).
- Não guardar token GitHub / senha SMTP / credencial de banco no frontend, em log
  ou em notebook.
- Não rodar `git` concorrente no mesmo workspace sem lock.

---

## 7. Sequência recomendada de entrega

1 → 2 → 3 → **4 (kernel)** → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13.

Fases 1–3 são baixo risco e destravam a UX de IDE. Fase 4 é o maior esforço e o
coração do produto. Fases 5–6 (Git) podem correr em paralelo com 7–9 por serem
áreas de código quase disjuntas. 10–11 são incrementos de superfície. 12–13
endurecem e validam.
