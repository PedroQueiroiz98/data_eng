from __future__ import annotations

from nbplatform.services.lsp.virtual_module import VirtualModule


def test_build_tracks_cell_starts_and_counts() -> None:
    vm = VirtualModule.build(["import os\nx = 1", "y = 2\n", "print(y)"])
    assert vm.cell_line_counts == (2, 2, 1)
    # célula 0 nas linhas 0..1; separador; célula 1 começa em 3; separador; célula 2 em 6
    assert vm.cell_starts == (0, 3, 6)
    assert "import os" in vm.source


def test_to_absolute_and_back_roundtrip() -> None:
    vm = VirtualModule.build(["a = 1\nb = 2", "c = 3\nd = 4"])
    abs_line, abs_col = vm.to_absolute(1, 1, 4)  # célula 1, 2ª linha, coluna 4
    assert (abs_line, abs_col) == (5, 4)
    cell, line, col = vm.to_cell(abs_line, abs_col)
    assert (cell, line, col) == (1, 1, 4)


def test_neutralize_keeps_line_count_for_magics() -> None:
    src = "%pip install pandas\n!ls -la\nimport pandas as pd\npd"
    vm = VirtualModule.build([src])
    assert vm.source.count("\n") == src.count("\n")
    assert "%pip" not in vm.source
    assert "!ls" not in vm.source
    assert "import pandas as pd" in vm.source


def test_neutralize_cell_magic_blanks_body() -> None:
    src = "%%sql\nSELECT * FROM clientes\nWHERE id = 1"
    vm = VirtualModule.build([src])
    assert "SELECT" not in vm.source
    assert vm.source.count("\n") == src.count("\n")


def test_to_cell_clamps_separator_line_to_previous_cell() -> None:
    vm = VirtualModule.build(["a = 1", "b = 2"])
    # linha 2 (1-based) é o separador em branco entre as células
    cell, line, _ = vm.to_cell(2, 0)
    assert cell == 0
    assert line == 0
