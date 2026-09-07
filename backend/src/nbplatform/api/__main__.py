"""`python -m nbplatform.api` — sobe o servidor Uvicorn."""

from __future__ import annotations

import uvicorn

from nbplatform.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "nbplatform.api.main:app",
        host="0.0.0.0",  # noqa: S104 - serviço em container
        port=settings.backend_port,
        log_config=None,  # usamos nosso logging estruturado
    )


if __name__ == "__main__":
    main()
