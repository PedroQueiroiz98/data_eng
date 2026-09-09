.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down logs build rebuild ps migrate revision test test-backend test-frontend lint fmt shell-backend psql redis-cli

help: ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Sobe o ambiente completo (build + up)
	$(COMPOSE) up --build

down: ## Derruba o ambiente e remove volumes
	$(COMPOSE) down -v

logs: ## Segue os logs de todos os serviços
	$(COMPOSE) logs -f

build: ## Builda as imagens
	$(COMPOSE) build

rebuild: ## Rebuild sem cache
	$(COMPOSE) build --no-cache

ps: ## Status dos serviços
	$(COMPOSE) ps

migrate: ## Aplica migrations Alembic
	$(COMPOSE) run --rm backend alembic upgrade head

revision: ## Cria migration nova: make revision m="mensagem"
	$(COMPOSE) run --rm backend alembic revision --autogenerate -m "$(m)"

test: test-backend test-frontend ## Roda todos os testes

test-backend: ## Testes do backend (migrations + pytest dentro do container)
	$(COMPOSE) run --rm -e APP_ENV=test -e NBP_INTEGRATION=1 \
		-e REDIS_URL=redis://redis:6379/1 -e NBP_WORKSPACE_DIR=/tmp/ws-test backend \
		sh -c "rm -rf /tmp/ws-test && alembic upgrade head && pytest -q"

test-frontend: ## Testes do frontend (vitest + tsc)
	$(COMPOSE) run --rm frontend sh -c "pnpm test && pnpm exec tsc --noEmit"

lint: ## Ruff + mypy no backend
	$(COMPOSE) run --rm backend sh -c "ruff check . && mypy src"

fmt: ## Formata o backend com ruff
	$(COMPOSE) run --rm backend ruff format .

shell-backend: ## Shell no container do backend
	$(COMPOSE) run --rm backend sh

psql: ## psql no Postgres
	$(COMPOSE) exec postgres psql -U nbplatform -d nbplatform

redis-cli: ## redis-cli no Redis
	$(COMPOSE) exec redis redis-cli
