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

# Chave de metadados própria (permitida pelo schema nbformat v4 — additionalProperties).
NBP_META_KEY = "nbplatform"
DEPENDENCIES_KEY = "dependencies"
MAX_DEPENDENCY_SPEC_LEN = 200


def read_dependencies(content: dict[str, Any]) -> list[str]:
    """Lista de requisitos pip declarada em `metadata.nbplatform.dependencies`.

    Aceita lista de strings ou texto multi-linha. Ignora linhas vazias e
    comentários (`#`). Sanitiza specs perigosos (controle/nova-linha) e limita
    o tamanho de cada entrada — os pacotes são passados como argv (sem shell).
    """
    meta = content.get("metadata")
    if not isinstance(meta, dict):
        return []
    section = meta.get(NBP_META_KEY)
    raw = section.get(DEPENDENCIES_KEY) if isinstance(section, dict) else None
    if isinstance(raw, str):
        items: list[Any] = raw.splitlines()
    elif isinstance(raw, list):
        items = list(raw)
    else:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        spec = item.split("#", 1)[0].strip()
        if not spec or len(spec) > MAX_DEPENDENCY_SPEC_LEN:
            continue
        if any(ch in spec for ch in ("\n", "\r", "\x00")):
            continue
        if spec.startswith("-"):  # nada de flags arbitrárias de pip
            continue
        if spec not in seen:
            seen.add(spec)
            out.append(spec)
    return out


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
