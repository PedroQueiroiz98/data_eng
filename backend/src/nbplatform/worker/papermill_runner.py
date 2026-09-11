"""Subprocesso que executa um notebook via Papermill.

Uso: python -m nbplatform.worker.papermill_runner <input.ipynb> <output.ipynb> <params.json> [cwd]

Contrato:
- stdout: linhas de log (a mãe encaminha para execution_logs + Redis).
- exit 0: sucesso. exit 3: erro de execução do notebook (PapermillExecutionError).
  exit 1: erro inesperado (setup, kernel, etc.).
- a última linha do stdout em caso de erro começa com "PAPERMILL_ERROR::".
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_NOTEBOOK_ERROR = 3


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print("PAPERMILL_ERROR::uso inválido do runner", flush=True)
        return EXIT_UNEXPECTED

    input_path, output_path, params_path = argv[:3]
    cwd = argv[3] if len(argv) == 4 else None
    _configure_logging()

    try:
        import papermill as pm
        from papermill.exceptions import PapermillExecutionError
    except Exception as exc:  # noqa: BLE001
        print(f"PAPERMILL_ERROR::import: {exc}", flush=True)
        return EXIT_UNEXPECTED

    parameters = json.loads(Path(params_path).read_text(encoding="utf-8") or "{}")

    kernel_name = _resolve_kernel(input_path)
    print(f"starting papermill (kernel={kernel_name}, params={list(parameters)})", flush=True)

    try:
        pm.execute_notebook(
            input_path,
            output_path,
            parameters=parameters,
            kernel_name=kernel_name,
            cwd=cwd,  # ancora o kernel na pasta do notebook (módulos locais, ex. etl/*)
            log_output=True,  # roteia stdout/stderr das células para o logger (stdout)
            progress_bar=False,
            request_save_on_cell_execute=True,
            execution_timeout=None,  # sem limite por célula — pipelines longas não são abortadas
        )
    except PapermillExecutionError as exc:
        print(f"PAPERMILL_ERROR::{exc.ename}: {exc.evalue}", flush=True)
        return EXIT_NOTEBOOK_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"PAPERMILL_ERROR::{type(exc).__name__}: {exc}", flush=True)
        return EXIT_UNEXPECTED

    print("papermill finalizado com sucesso", flush=True)
    return EXIT_OK


def _resolve_kernel(input_path: str) -> str:
    """Usa o kernelspec do notebook se existir; senão python3."""
    try:
        nb = json.loads(Path(input_path).read_text(encoding="utf-8"))
        name = nb.get("metadata", {}).get("kernelspec", {}).get("name")
        if isinstance(name, str) and name:
            return name
    except Exception:  # noqa: BLE001
        pass
    return "python3"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
