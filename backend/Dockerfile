FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ============================================================
# Dependências do sistema
# ============================================================
#
# git:
#   operações de repositório do Workspace
#
# unixodbc:
#   fornece libodbc.so.2 para pyodbc
#
# unixodbc-dev:
#   headers/bibliotecas necessárias para componentes ODBC
#
# libpq5:
#   biblioteca cliente PostgreSQL
#
# ca-certificates:
#   certificados TLS
#
# curl + gnupg:
#   usados para instalar o Microsoft ODBC Driver
# ============================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        curl \
        gnupg \
        unixodbc \
        unixodbc-dev \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Microsoft ODBC Driver 18 for SQL Server
# ============================================================

RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor \
    -o /usr/share/keyrings/microsoft-prod.gpg

RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/microsoft-prod.list

RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# uv
# ============================================================

RUN pip install --no-cache-dir uv

# ============================================================
# Python dependencies
# ============================================================

COPY pyproject.toml README.md ./

COPY src/nbplatform/__init__.py \
     src/nbplatform/__init__.py

COPY src/workspace_sdk/__init__.py \
     src/workspace_sdk/__init__.py

RUN uv pip install \
    --system \
    --no-cache \
    -e ".[dev]"

# ============================================================
# Python kernel utilizado pelo Papermill
# ============================================================

RUN python -m ipykernel install \
    --name python3 \
    --display-name "Python 3"

# ============================================================
# Código da aplicação
# ============================================================

COPY . .

# ============================================================
# Diretórios de dados
# ============================================================

RUN mkdir -p \
    /data/executions \
    /data/workspaces \
    /data/workspace

# ============================================================
# Usuário não-root
# ============================================================

RUN useradd \
    --create-home \
    --uid 1000 \
    app \
    && chown -R app:app /app /data

USER app

EXPOSE 8000

# ============================================================
# Comando padrão
# ============================================================

CMD ["python", "-m", "nbplatform.api"]