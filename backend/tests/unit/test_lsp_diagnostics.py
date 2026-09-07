from __future__ import annotations

from nbplatform.services.lsp.diagnostics import analyze


def test_syntax_error_is_reported_as_error() -> None:
    diags = analyze("def f(:\n    pass\n")
    assert diags
    assert diags[0].severity == "error"
    assert diags[0].source == "syntax"


def test_undefined_name_is_error() -> None:
    diags = analyze("print(undefined_variable_xyz)\n")
    assert any(d.severity == "error" and "undefined_variable_xyz" in d.message for d in diags)


def test_unused_import_is_warning() -> None:
    diags = analyze("import os\nx = 1\n")
    assert any(d.severity == "warning" and "os" in d.message for d in diags)
    assert all(d.source == "pyflakes" for d in diags)


def test_clean_code_has_no_diagnostics() -> None:
    assert analyze("x = 1\ny = x + 2\nprint(y)\n") == []
