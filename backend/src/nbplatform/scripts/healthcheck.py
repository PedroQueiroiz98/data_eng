"""Healthcheck de container: `python -m nbplatform.scripts.healthcheck`.

Sai 0 se `GET /health` responder 200, senão 1. Sem dependências externas.
"""

from __future__ import annotations

import sys
import urllib.request

from nbplatform.core.config import get_settings


def main() -> int:
    port = get_settings().backend_port
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310 - URL local fixa
            return 0 if resp.status == 200 else 1
    except Exception as exc:  # noqa: BLE001
        print(f"healthcheck falhou: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
