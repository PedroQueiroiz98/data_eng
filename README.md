# nbplatform

Plataforma web para criar, editar, executar e orquestrar **notebooks Python**, usando
**Papermill** como executor oficial. A aplicação controla workflows, jobs, retries, timeouts,
logs, agendamento e segurança — o Papermill apenas executa os notebooks.

> Status: **Fase 1 — Infraestrutura**. As fases seguintes (Notebook, Papermill, Resiliência,
> Workflow, Jobs, Scheduler, Segurança, Observabilidade) são entregues em sequência.

## Arquitetura

```
React ──REST/WS──> FastAPI ──> PostgreSQL
                       │  └──> Redis (fila + eventos)
                       │            │
                   APScheduler      ├──> Worker ──> Papermill ──> Jupyter Kernel ──> output.ipynb
                  (só cria Jobs)    │
                                    └──> (Fase 8) isolamento em container Docker
```

Regra inviolável: **a API nunca executa código do usuário**. Nada de `exec`. Todo notebook roda
via Papermill dentro do Worker.

### Componentes

| Serviço     | Imagem              | Papel                                                        |
| ----------- | ------------------- | ----------------------------------------------------------- |
| `backend`   | `./backend`         | API FastAPI (`python -m nbplatform.api`)                     |
| `worker`    | `./backend`         | Consumidor da fila + Papermill (`python -m nbplatform.worker`) |
| `scheduler` | `./backend`         | APScheduler → cria Jobs (`python -m nbplatform.scheduler`)   |
| `frontend`  | `./frontend`        | React + Vite + Tailwind                                      |
| `postgres`  | `postgres:16`       | Estado do domínio                                            |
| `redis`     | `redis:7`           | Fila, DLQ, canal de eventos, heartbeats                      |

Backend, worker e scheduler são **o mesmo pacote Python** (`nbplatform`) com três entrypoints,
compartilhando modelos, domínio e configuração. A máquina de estados, o `RetryPolicy` e a
classificação de erro vivem num único lugar (`nbplatform/domain/`).

## Como rodar (Docker)

Pré-requisitos: Docker + Docker Compose.

```bash
cp .env.example .env          # ajuste se quiser; nunca comite .env
docker compose up --build     # ou: make up
```

Serviços expostos:

- API: <http://localhost:8000> — `GET /health`, `GET /ready`, `/api/notebooks`, docs em `/docs`
- Frontend: <http://localhost:5173> — **Dashboard** (saúde dos serviços) e **Notebooks** (CRUD + editor Monaco)

Encerrar e limpar volumes:

```bash
docker compose down -v        # ou: make down
```

### Health checks

| Endpoint  | Significado                                                                    |
| --------- | ---------------------------------------------------------------------------- |
| `/health` | Liveness — o processo está de pé (não toca em dependências).                  |
| `/ready`  | Readiness — Postgres, Redis, Worker e Scheduler respondendo. 200 ou 503.     |

Worker e Scheduler publicam heartbeat em Redis (`nbp:heartbeat:<serviço>`, com TTL); `/ready`
considera o serviço saudável se o heartbeat tiver menos de `WORKER_LEASE_TIMEOUT_S` segundos.

## Notebooks (Fase 2)

Notebooks são armazenados no formato padrão `.ipynb` (nbformat v4) — o metadado fica em
`notebooks`, o conteúdo em `notebook_versions` (**versões imutáveis**). Cada save cria uma
versão nova e incrementa `current_version`; versões antigas nunca mudam. Toda futura Execution
(Fase 3) aponta para um `notebook_version_id` específico → reprodutibilidade.

| Método | Rota | Descrição |
| ------ | ---- | --------- |
| `GET`    | `/api/notebooks` | lista (paginado: `limit`, `offset`) |
| `POST`   | `/api/notebooks` | cria (opcional `content`; sem ele, gera notebook vazio com célula `parameters`) |
| `GET`    | `/api/notebooks/{id}` | metadados + conteúdo da versão atual + `version_count` |
| `PUT`    | `/api/notebooks/{id}` | atualiza **só** `name`/`description` |
| `DELETE` | `/api/notebooks/{id}` | remove notebook e todas as versões |
| `POST`   | `/api/notebooks/{id}/versions` | salva novo `.ipynb` → nova versão imutável |
| `GET`    | `/api/notebooks/{id}/versions` | lista versões (sem conteúdo) |
| `GET`    | `/api/notebooks/{id}/versions/{n}` | uma versão com conteúdo |

Conteúdo inválido (não é `.ipynb` v4 válido) → `422 {"error":{"code":"validation_error"}}`.
Recurso inexistente → `404 {"error":{"code":"not_found"}}`.

**Editor** (`/notebooks/:id`): Monaco (bundle local, sem CDN); adicionar/remover/duplicar/mover
célula, alternar code↔markdown↔raw, editar, salvar versão, e **Executar** (dispara o notebook
inteiro via Papermill com parâmetros JSON).

## Execução / Papermill (Fase 3)

`POST /api/notebooks/{id}/execute` cria uma `Execution` (`QUEUED`), enfileirada no Redis. O
**Worker** consome a fila (`BLMOVE` principal → *processing*), materializa `input.ipynb` da
versão do notebook, roda `papermill.execute_notebook` **num subprocesso** (isolamento por
processo; container Docker vem na Fase 8), transmite logs em tempo real, persiste o
`output.ipynb` e o status final.

Estados: `QUEUED → RUNNING → {SUCCESS | FAILED | TIMEOUT | CANCELLED}` — transições inválidas
são rejeitadas pela state machine (`domain/state_machine.py`). Parâmetros são injetados pelo
Papermill (célula com tag `parameters`). Timeout via `EXECUTION_TIMEOUT_S` (mata o subprocesso
→ `TIMEOUT`). `MAX_CONCURRENT_EXECUTIONS` limita execuções simultâneas por worker (excedente
fica `QUEUED`).

| Método | Rota | Descrição |
| ------ | ---- | --------- |
| `POST` | `/api/notebooks/{id}/execute` | dispara execução; body `{parameters, notebook_version_number?, idempotency_key?}` → `202` |
| `GET`  | `/api/executions?status=&limit=&offset=` | lista |
| `GET`  | `/api/executions/{id}` | detalhe (status, tempos, erro, `has_output`) |
| `GET`  | `/api/executions/{id}/logs?after_seq=` | logs a partir de um cursor |
| `GET`  | `/api/executions/{id}/output` | `output.ipynb` executado (404 enquanto não há) |
| `WS`   | `/ws/executions/{id}?after_seq=` | snapshot + eventos `status_changed` / `log` / `output` / `progress` |

O front (`/executions`, `/executions/:id`) usa o WebSocket com **reconexão automática**:
ao reconectar, retoma os logs a partir do último `seq` recebido; um polling REST serve de
fallback. `idempotency_key` evita execuções duplicadas.

> Execução de **célula individual** contra um kernel vivo (estilo Jupyter) é um mecanismo
> distinto do executor Papermill e está fora do escopo desta fase.

## Resiliência (Fase 4)

- **RetryPolicy** (`domain/retry_policy.py`) — backoff exponencial (`initial_delay * multiplier^(n-1)`,
  capado em `max_delay`), `retry_mode` `ANY` | `TRANSIENT_ONLY`. Lógica num só lugar.
- **Classificação de erro** (`domain/error_classification.py`) — `TRANSIENT` / `PERMANENT` /
  `UNKNOWN` por código interno + marcadores na mensagem (ex.: `NameError` → PERMANENT;
  `OperationalError`/`503` → TRANSIENT; `LEASE_EXPIRED` → TRANSIENT).
- **Retry automático** — ao falhar, o `RetryCoordinator` decide: re-enfileirar com atraso
  (ZSET `nbp:queue:executions:delayed`, promovido pelo worker) ou **DLQ** (`nbp:dlq:executions`)
  quando os retries esgotam ou o erro não é elegível. O evento WS emitido é o status final
  (retry → `QUEUED`, não `FAILED`).
- **Timeout** — subprocesso morto ao exceder `EXECUTION_TIMEOUT_S` → `TIMEOUT`.
- **Cancelamento** — `POST /api/executions/{id}/cancel` (idempotente): `QUEUED` → `CANCELLED`
  direto; `RUNNING` → sinaliza `nbp:cancel:<id>`, o worker termina o subprocesso e transiciona.
- **Retry manual** — `POST /api/executions/{id}/retry`: `FAILED`/`TIMEOUT` → `QUEUED`
  (attempt+1, enfileirado na hora).
- **Recovery** (`worker/recovery.py`) — a cada `RECOVERY_INTERVAL_S`, `RUNNING` com
  `last_heartbeat` além de `WORKER_LEASE_TIMEOUT_S` → falha a tentativa (`LEASE_EXPIRED`) e
  aplica retry/DLQ. `SELECT ... FOR UPDATE SKIP LOCKED` evita corrida entre workers. Nunca
  fica preso em `RUNNING`.

Config em `.env.example` (`NBP_EXECUTION_MAX_RETRIES`, `NBP_EXECUTION_RETRY_MODE`, delays,
`NBP_RECOVERY_INTERVAL_S`).

## Workflows (Fase 5)

Um **Workflow** é um DAG de tarefas. Tarefa tipo `NOTEBOOK` (único suportado nesta fase):
notebook + parâmetros + `timeout_s` + `max_retries` + `retry_policy`. `workflow_dependencies`
guarda as arestas; o backend valida que o grafo **não tem ciclo** (Kahn, `domain/dag.py`) —
o front não é a única validação.

| Método | Rota | Descrição |
| ------ | ---- | --------- |
| `GET/POST` | `/api/workflows` | lista / cria (DRAFT, vazio) |
| `GET` | `/api/workflows/{id}` | detalhe com `tasks` + `dependencies` |
| `PUT` | `/api/workflows/{id}` | metadados (`name`, `description`, `status`) |
| `DELETE` | `/api/workflows/{id}` | remove |
| `PUT` | `/api/workflows/{id}/graph` | **substitui** tasks+arestas transacionalmente |

`PUT …/graph` recebe `{tasks:[{key,name,notebook_id,parameters,timeout_s,max_retries,retry_policy,ui_position}], dependencies:[{from_key,to_key}]}`.
O `key` é o id da task existente (preserva o id) ou um id temporário (cria nova); tasks
ausentes são removidas. Rejeita (`422`) ciclo, aresta para tarefa fora do grafo, tipo ≠
`NOTEBOOK` e `notebook_id` inexistente.

**Editor** (`/workflows/:id`): canvas React Flow (`@xyflow/react`) — adicionar/remover nó,
conectar por arraste, painel lateral (nome, notebook, timeout, retries), salvar, **Executar**.

## Jobs (Fase 6)

Executar um Workflow cria um **Job**. O `JobOrchestrator` cria um `JobTask` por tarefa
(`PENDING`), enfileira o *ready-set* (tarefas sem dependência) criando uma `Execution` por
task (com `retry_policy`/`timeout_s` herdados da `workflow_task`), e o **loop de orquestração
do worker** (`sync_and_advance`, a cada ~2s, `SELECT … FOR UPDATE SKIP LOCKED` na linha do
Job) avança o DAG:

- Execution da task termina → copia o status para o `JobTask`.
- Tarefa `PENDING` com todas as dependências `SUCCESS` → cria Execution + enfileira.
- Dependência `FAILED`/`CANCELLED`/`SKIPPED` → tarefa vira **`SKIPPED`** (propaga).
- Todas terminais → Job `SUCCESS` (todas ok), senão `FAILED` (ou `CANCELLED`).
- Tarefas independentes rodam **em paralelo** (limitado por `MAX_CONCURRENT_EXECUTIONS`).

| Método | Rota | Descrição |
| ------ | ---- | --------- |
| `POST` | `/api/workflows/{id}/run` | cria e inicia o Job (`202`), body `{parameters}` |
| `GET`  | `/api/jobs?workflow_id=&status=` | lista |
| `GET`  | `/api/jobs/{id}` | detalhe: tasks (com `name`, `execution_id`) + dependências |
| `GET`  | `/api/jobs/{id}/logs?after_seq=` | timeline de orquestração |
| `POST` | `/api/jobs/{id}/cancel` | idempotente; pendências → CANCELLED, running recebe sinal |
| `POST` | `/api/jobs/{id}/retry` | Job terminal com falha → re-arma tasks FAILED/SKIPPED/CANCELLED (mantém SUCCESS) |
| `WS`   | `/ws/jobs/{id}?after_seq=` | snapshot (job + tasks + logs) + eventos |

UI: `/jobs` (lista estilo GitHub Actions, ✓/✕/○ + duração) e `/jobs/:id` (tasks com status +
link para os logs da Execution + timeline ao vivo por WebSocket). Botão **Executar** no editor
de workflow leva ao Job.

## Desenvolvimento

### Backend

```bash
cd backend
uv sync                       # cria .venv com deps + dev deps
uv run alembic upgrade head   # requer Postgres acessível (DATABASE_URL)
uv run pytest -q
uv run ruff check . && uv run mypy src
```

Requisitos locais: Python 3.12+, `uv`. Sem eles, use os alvos do `Makefile` que rodam tudo
dentro dos containers (`make test-backend`, `make lint`, `make migrate`).

### Frontend

```bash
cd frontend
pnpm install
pnpm dev            # http://localhost:5173
pnpm test           # vitest
pnpm typecheck      # tsc --noEmit (strict)
```

Requisitos locais: Node 20+, pnpm 9+. Alternativa em container: `make test-frontend`.

### Migrations

Migrations são geradas por **autogenerate** do Alembic (`alembic/versions/`, com `env.py`
async apontando para `Base.metadata`). Fluxo:

```bash
make revision m="add coluna X em executions"   # gera a partir do diff modelos↔banco
make migrate                                   # alembic upgrade head
```

O `backend` roda `alembic upgrade head` no start.

## Modelo de domínio (resumo)

```
Notebook 1─* NotebookVersion        (versões imutáveis; toda Execution aponta para uma)
Notebook 1─* Execution              (execução de um notebook via Papermill)

Workflow 1─* WorkflowTask
Workflow 1─* WorkflowDependency     (arestas do DAG; validado sem ciclos no backend)

Workflow 1─* Job                    (execução concreta de um workflow)
Job      1─* JobTask ─? Execution
Job      1─* JobLog

Schedule, Variable, Secret, AuditLog, User
```

Estados de `Execution`: `QUEUED → RUNNING → {SUCCESS | FAILED | CANCELLED | TIMEOUT}`,
com `FAILED → QUEUED` (retry). Transições inválidas são rejeitadas pela state machine
(Fase 4).

## Configuração

Todas as variáveis em `.env.example`. Destaques:

| Variável                     | Default | Descrição                                  |
| ---------------------------- | ------- | ------------------------------------------ |
| `MAX_CONCURRENT_EXECUTIONS`  | 5       | Execuções simultâneas; excedente fica `QUEUED` |
| `MAX_CONCURRENT_JOBS`        | 5       | Jobs simultâneos                           |
| `EXECUTION_TIMEOUT_S`        | 1800    | Timeout padrão de execução                 |
| `WORKER_HEARTBEAT_INTERVAL_S`| 10      | Intervalo de heartbeat do worker/scheduler |
| `WORKER_LEASE_TIMEOUT_S`     | 60      | Lease; acima disso a execução é considerada abandonada |
| `SECRET_ENCRYPTION_KEY`      | —       | Chave Fernet para secrets (Fase 8). Gere uma real. |

## Roadmap por fase

1. **Infraestrutura** ✅ — monorepo, Docker Compose, Postgres, Redis, FastAPI, React, health checks.
2. **Notebook** ✅ — CRUD, versionamento imutável, editor Monaco, salvar `.ipynb` (nbformat v4).
3. **Papermill** ✅ — Execution, Worker (fila Redis + subprocesso), output.ipynb, logs, status, WebSocket com replay.
4. **Resiliência** ✅ — RetryPolicy + classificação de erro, retry auto (backoff + delayed queue) e manual, timeout, cancelamento, recovery de lease expirado, DLQ.
5. **Workflow** ✅ — CRUD, editor React Flow, DAG com detecção de ciclo no backend, save transacional do grafo.
6. **Jobs** ✅ — `POST /workflows/{id}/run`, orquestrador (ready-set, paralelismo, SKIPPED em cascata), cancel/retry, `/ws/jobs/{id}`, UI GitHub Actions.
7. Scheduler — cron, ativar/desativar, execução automática.
8. Segurança — auth/authz, secrets criptografados + masking, isolamento Docker, auditoria.
9. Observabilidade — métricas Prometheus, logs estruturados, readiness completo.
