FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# git: operações de repositório do Workspace (clone/pull/commit/push via CLI).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instala uv (resolver/instalador rápido de dependências).
RUN pip install --no-cache-dir uv

# Instala dependências primeiro para aproveitar cache de layer.
COPY pyproject.toml README.md ./
COPY src/nbplatform/__init__.py src/nbplatform/__init__.py
COPY src/workspace_sdk/__init__.py src/workspace_sdk/__init__.py
RUN uv pip install --system --no-cache -e ".[dev]"

# Registra o kernelspec 'python3' usado pelo Papermill.
RUN python -m ipykernel install --name python3 --display-name "Python 3"

# Copia o restante do código.
COPY . .

# Diretórios de dados (artefatos de execução + raízes de Workspace).
RUN mkdir -p /data/executions /data/workspaces

# Usuário não-root.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app /data
USER app

EXPOSE 8000

# Comando padrão sobrescrito pelo docker-compose por serviço (api / worker / scheduler).
CMD ["python", "-m", "nbplatform.api"]
