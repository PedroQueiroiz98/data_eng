"""Monta um módulo Python virtual a partir das células do notebook.

- Concatena as células na ordem do notebook (uma linha em branco separa cada uma).
- Neutraliza magics de Jupyter (`%pip`, `!cmd`, `%%sql`, ...) preservando a
  contagem de linhas, para o Jedi não engasgar.
- Converte posições (célula, linha, coluna) 0-based ⟷ posição absoluta no
  módulo virtual (linha 1-based / coluna 0-based, como o Jedi espera).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINE_MAGIC = re.compile(r"^(\s*)([%!].*)$")
_CELL_MAGIC = re.compile(r"^\s*%%")


def _neutralize(source: str) -> str:
    """Troca linhas de magic por `pass`/vazio mantendo o número de linhas."""
    lines = source.split("\n")
    out: list[str] = []
    cell_magic = False
    for i, line in enumerate(lines):
        if i == 0 and _CELL_MAGIC.match(line):
            cell_magic = True
            out.append("pass" + " " * max(0, len(line) - 4))
            continue
        if cell_magic:
            out.append("")  # corpo do cell-magic (ex.: SQL) — ignorado
            continue
        m = _LINE_MAGIC.match(line)
        if m:
            indent = m.group(1)
            out.append(f"{indent}pass")
        else:
            out.append(line)
    return "\n".join(out)


@dataclass(frozen=True)
class VirtualModule:
    source: str
    """Fonte concatenada e neutralizada."""
    cell_starts: tuple[int, ...]
    """Linha 0-based onde cada célula começa no módulo virtual."""
    cell_line_counts: tuple[int, ...]
    """Número de linhas de cada célula (original)."""

    @classmethod
    def build(cls, cells: list[str]) -> VirtualModule:
        starts: list[int] = []
        counts: list[int] = []
        chunks: list[str] = []
        cursor = 0
        for raw in cells:
            neutral = _neutralize(raw)
            n_lines = neutral.count("\n") + 1
            starts.append(cursor)
            counts.append(n_lines)
            chunks.append(neutral)
            cursor += n_lines + 1  # +1 pela linha em branco separadora
        source = "\n\n".join(chunks) if chunks else ""
        return cls(source=source, cell_starts=tuple(starts), cell_line_counts=tuple(counts))

    # ── mapeamento de posições ──────────────────────────────────────────────
    def to_absolute(self, cell_index: int, line: int, column: int) -> tuple[int, int]:
        """(célula, linha 0-based, coluna 0-based) → (linha 1-based, coluna 0-based)."""
        if cell_index < 0 or cell_index >= len(self.cell_starts):
            raise IndexError(f"célula {cell_index} fora do intervalo")
        abs_line0 = self.cell_starts[cell_index] + max(0, line)
        return abs_line0 + 1, max(0, column)

    def to_cell(self, abs_line_1based: int, column: int) -> tuple[int, int, int]:
        """(linha 1-based, coluna) → (célula, linha 0-based na célula, coluna)."""
        abs_line0 = abs_line_1based - 1
        cell_index = 0
        for i, start in enumerate(self.cell_starts):
            if abs_line0 >= start:
                cell_index = i
            else:
                break
        line_in_cell = abs_line0 - self.cell_starts[cell_index]
        # se caiu na linha separadora, prende no fim da célula
        max_line = self.cell_line_counts[cell_index] - 1
        line_in_cell = min(max(0, line_in_cell), max_line)
        return cell_index, line_in_cell, max(0, column)

    def in_notebook(self, module_path: str | None) -> bool:
        """True quando a posição do Jedi aponta para o próprio módulo virtual."""
        return module_path in (None, "", "<string>")
