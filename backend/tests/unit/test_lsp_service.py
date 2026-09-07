from __future__ import annotations

import pytest

from nbplatform.core.config import get_settings
from nbplatform.services.lsp.service import LspService


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def svc() -> LspService:
    return LspService()


async def test_completion_on_list_variable_suggests_list_methods(svc: LspService) -> None:
    cells = ["clientes = []", "clientes."]
    r = await svc.complete(cells, cell_index=1, line=0, column=len("clientes."))
    assert r.ok
    labels = {c.label for c in r.completions}
    assert {"append", "extend", "sort"} <= labels


async def test_completion_uses_notebook_context_from_previous_cells(svc: LspService) -> None:
    cells = ["def process_data():\n    return 42", "resultado = process_data()", "process_"]
    r = await svc.complete(cells, cell_index=2, line=0, column=len("process_"))
    assert r.ok
    assert any(c.label == "process_data" for c in r.completions)


async def test_completion_filters_sensitive_names(svc: LspService) -> None:
    cells = ["api_key = 'super-secret-value'\napikey_public = 1", "api"]
    r = await svc.complete(cells, cell_index=1, line=0, column=3)
    assert r.ok
    assert all(c.label != "api_key" for c in r.completions)


async def test_hover_returns_docstring(svc: LspService) -> None:
    cells = ["def greet(name):\n    '''Say hi to name.'''\n    return name", "greet"]
    r = await svc.hover(cells, cell_index=1, line=0, column=3)
    assert r.ok
    assert r.hover is not None
    assert "hi to name" in r.hover.documentation.lower()


async def test_signature_help_reports_parameters(svc: LspService) -> None:
    cells = ["def total(items, tax=0.0, discount=None):\n    return 0", "total("]
    r = await svc.signature(cells, cell_index=1, line=0, column=len("total("))
    assert r.ok
    assert r.signature is not None
    assert any("items" in p for p in r.signature.parameters)


async def test_definition_points_to_defining_cell(svc: LspService) -> None:
    cells = [
        "import os",
        "def build_report():\n    return 'ok'",
        "x = 1",
        "build_report()",
    ]
    r = await svc.definition(cells, cell_index=3, line=0, column=2)
    assert r.ok
    assert r.locations
    loc = r.locations[0]
    assert loc.external is False
    assert loc.cell_index == 1
    assert loc.line == 0


async def test_references_finds_all_usages(svc: LspService) -> None:
    cells = [
        "def run():\n    return 1",
        "run()\nrun()",
        "y = run()",
    ]
    r = await svc.references(cells, cell_index=0, line=0, column=4)
    assert r.ok
    # definição + 3 usos
    assert len(r.locations) >= 4


async def test_auto_import_suggests_pandas_for_dataframe(svc: LspService) -> None:
    r = await svc.auto_import("DataFrame")
    assert r.ok
    assert any("pandas" in s.module for s in r.imports)


async def test_disabled_via_settings_returns_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LSP_ENABLED", "false")
    get_settings.cache_clear()
    try:
        r = await LspService().complete(["x."], cell_index=0, line=0, column=2)
        assert r.ok is False
    finally:
        monkeypatch.delenv("LSP_ENABLED", raising=False)
        get_settings.cache_clear()


async def test_health_reports_engine(svc: LspService) -> None:
    h = svc.health()
    assert h["engine"] == "jedi"
    assert h["enabled"] is True
