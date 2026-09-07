# nbplatform — backend

Pacote Python único com três entrypoints que compartilham modelos, domínio e configuração:

| Entrypoint | Comando                          | Papel                                  |
| ---------- | -------------------------------- | -------------------------------------- |
| API        | `python -m nbplatform.api`       | FastAPI (REST + WebSocket)             |
| Worker     | `python -m nbplatform.worker`    | Consome a fila e executa via Papermill |
| Scheduler  | `python -m nbplatform.scheduler` | APScheduler — só cria Jobs             |

Consulte o `README.md` da raiz do monorepo para instruções de execução com Docker Compose.

## Layout

```
src/nbplatform/
├── core/        config, logging estruturado, crypto
├── db/          engine async + session (SQLAlchemy 2.x)
├── domain/      enums e regras puras (state machine, retry, DAG, classificação de erro)
├── models/      tabelas SQLAlchemy
├── schemas/     modelos Pydantic v2 (I/O da API)
├── queue/       fila Redis + canal de eventos
├── services/    regras de negócio (sem lógica nas rotas)
├── api/         app FastAPI
├── worker/      loop do worker
├── scheduler/   adapter APScheduler
└── scripts/     utilitários (healthcheck de container, seed)
```
