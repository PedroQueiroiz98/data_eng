"""Manipulação do formato `.ipynb` (nbformat v4). Nada de formato próprio."""

from __future__ import annotations

import warnings
from typing import Any

import nbformat
from nbformat import NotebookNode
from nbformat.validator import NotebookValidationError, normalize

from nbplatform.core.errors import DomainValidationError

NBFORMAT_MAJOR = 4
NBFORMAT_MINOR = 5

PARAMETERS_TAG = "parameters"


def new_empty_notebook() -> dict[str, Any]:
    """Notebook v4 com uma célula de código vazia e uma célula de parâmetros."""
    nb = nbformat.v4.new_notebook()
    params = nbformat.v4.new_code_cell(source="# Parameters\n")
    params.metadata["tags"] = [PARAMETERS_TAG]
    nb.cells = [params, nbformat.v4.new_code_cell(source="")]
    nb.metadata.setdefault("language_info", {"name": "python"})
    nb.metadata.setdefault("kernelspec", {"name": "python3", "display_name": "Python 3"})
    return _to_plain_dict(nb)


def validate_notebook(content: Any) -> dict[str, Any]:
    """Valida e normaliza para nbformat v4. Levanta `DomainValidationError` se inválido."""
    if not isinstance(content, dict):
        raise DomainValidationError("O conteúdo do notebook deve ser um objeto JSON.")
    try:
        node: NotebookNode = nbformat.from_dict(content)
        node = _upgrade_to_v4(node)
        # normaliza (adiciona `id` de célula ausente, etc.) antes de validar;
        # normalize() emite avisos justamente sobre o que está corrigindo.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, node = normalize(node)
        nbformat.validate(node)
    except NotebookValidationError as exc:
        raise DomainValidationError(f"Notebook .ipynb inválido: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - qualquer erro de parsing vira 422
        raise DomainValidationError(f"Não foi possível ler o notebook: {exc}") from exc
    return _to_plain_dict(node)


def has_parameters_cell(content: dict[str, Any]) -> bool:
    for cell in content.get("cells", []):
        tags = cell.get("metadata", {}).get("tags", [])
        if PARAMETERS_TAG in tags:
            return True
    return False


def _upgrade_to_v4(node: NotebookNode) -> NotebookNode:
    major = int(node.get("nbformat", NBFORMAT_MAJOR))
    if major < NBFORMAT_MAJOR:
        return nbformat.convert(node, to_version=NBFORMAT_MAJOR)
    return node


def _to_plain_dict(node: NotebookNode) -> dict[str, Any]:
    """NotebookNode -> dict puro serializável (sem subclasses de dict)."""
    import json

    result: dict[str, Any] = json.loads(nbformat.writes(node))
    return result
