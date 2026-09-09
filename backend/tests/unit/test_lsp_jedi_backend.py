from __future__ import annotations

from nbplatform.services.lsp import jedi_backend


def test_warmup_does_not_raise() -> None:
    # idempotente (lru_cache) e aquece os dois caminhos sem levantar
    jedi_backend.warmup()
    jedi_backend.warmup()


def test_complete_ignores_workspace_root_and_stays_on_fast_path() -> None:
    src = "clientes = []\nclientes."
    a = jedi_backend.complete(src, 2, len("clientes."), "", 50)
    b = jedi_backend.complete(src, 2, len("clientes."), "", 50, 0, "/nonexistent/dir")
    labels_a = {c.label for c in a}
    labels_b = {c.label for c in b}
    assert {"append", "extend", "sort"} <= labels_a
    assert labels_a == labels_b


def test_complete_marks_callables() -> None:
    src = "def carrega():\n    return 1\ncarrega"
    items = jedi_backend.complete(src, 3, len("carrega"), "", 50)
    item = next(c for c in items if c.label == "carrega")
    assert item.call is True
    inst = next((c for c in items if not c.call), None)
    # variáveis/instâncias existem e não são chamáveis
    if inst is not None:
        assert inst.call is False


def test_complete_signature_scan_fills_detail_for_first_callables() -> None:
    src = "def total(items, tax=0.0):\n    return 0\ntot"
    items = jedi_backend.complete(src, 3, len("tot"), "", 50, signature_scan=12)
    item = next(c for c in items if c.label == "total")
    assert "items" in item.detail


def test_resolve_returns_docstring_for_known_symbol() -> None:
    src = "def greet(name):\n    '''Say hi to name.'''\n    return name\ngreet"
    r = jedi_backend.resolve(src, 4, len("greet"), "greet", "")
    assert r is not None
    assert "hi to name" in r.documentation.lower()
    assert r.call is True


def test_resolve_unknown_label_returns_none() -> None:
    src = "x = 1\nx"
    assert jedi_backend.resolve(src, 2, 1, "does_not_exist", "") is None


def test_goto_still_resolves_in_buffer_definition() -> None:
    src = "def build():\n    return 1\nbuild()"
    locs = jedi_backend.goto(src, 3, 2, "", None)
    assert locs
    assert locs[0].external is False
    assert locs[0].line == 1
