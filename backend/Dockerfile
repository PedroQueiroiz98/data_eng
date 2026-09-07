FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instala uv (resolver/instalador rápido de dependências).
RUN pip install --no-cache-dir uv

# Instala dependências primeiro para aproveitar cache de layer.
COPY pyproject.toml README.md ./
COPY src/nbplatform/__init__.py src/nbplatform/__init__.py
RUN uv pip install --system --no-cache -e ".[dev]"

# Registra o kernelspec 'python3' usado pelo Papermill.
RUN python -m ipykernel install --name python3 --display-name "Python 3"

# Copia o restante do código.
COPY . .

# Diretório de artefatos de execução (input/output .ipynb).
RUN mkdir -p /data/executions

# Usuário não-root.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app /data
USER app

EXPOSE 8000

# Comando padrão sobrescrito pelo docker-compose por serviço (api / worker / scheduler).
CMD ["python", "-m", "nbplatform.api"]
