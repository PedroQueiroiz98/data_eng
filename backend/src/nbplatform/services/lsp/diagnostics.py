"""Diagnósticos estáticos: SyntaxError (compile) + pyflakes.

Type-checking real (ex.: `DataFrame has no attribute X`) fica para uma fase
futura com basedpyright opcional. Aqui cobrimos sintaxe e nomes indefinidos /
imports não usados / redefinições, que já pegam a maior parte dos erros de quem
está escrevendo notebook.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from pyflakes import api as pyflakes_api  # type: ignore[import-untyped]
from pyflakes import messages as pyflakes_messages

_ERROR_MESSAGES = tuple(
    m
    for m in (
        getattr(pyflakes_messages, name, None)
        for name in (
            "UndefinedName",
            "UndefinedLocal",
            "DuplicateArgument",
            "ReturnOutsideFunction",
            "YieldOutsideFunction",
            "ContinueOutsideLoop",
            "BreakOutsideLoop",
        )
    )
    if isinstance(m, type)
)


@dataclass(frozen=True)
class RawDiagnostic:
    line: int  # 1-based, absoluto no módulo virtual
    column: int  # 0-based
    end_column: int | None
    severity: str  # "error" | "warning"
    message: str
    source: str  # "syntax" | "pyflakes"
    code: str


class _Collector:
    """Duck-type do `pyflakes.reporter.Reporter` (só os 3 métodos que ele chama)."""

    def __init__(self) -> None:
        self.items: list[RawDiagnostic] = []

    def unexpectedError(self, _filename: str, msg: str) -> None:  # noqa: N802
        self.items.append(
            RawDiagnostic(1, 0, None, "warning", str(msg), "pyflakes", "unexpected")
        )

    def syntaxError(  # noqa: N802
        self,
        _filename: str,
        msg: str,
        lineno: int,
        offset: int | None,
        _text: str | None,
    ) -> None:
        col = max(0, (offset or 1) - 1)
        self.items.append(
            RawDiagnostic(max(1, lineno), col, None, "error", str(msg), "syntax", "syntax-error")
        )

    def flake(self, message: pyflakes_messages.Message) -> None:
        severity = "error" if isinstance(message, _ERROR_MESSAGES) else "warning"
        col = getattr(message, "col", 0) or 0
        try:
            text = message.message % message.message_args
        except Exception:  # noqa: BLE001
            text = message.message
        self.items.append(
            RawDiagnostic(
                line=message.lineno,
                column=col,
                end_column=None,
                severity=severity,
                message=text,
                source="pyflakes",
                code=type(message).__name__,
            )
        )


def analyze(source: str) -> list[RawDiagnostic]:
    """Roda compile() + pyflakes sobre a fonte do módulo virtual."""
    collector = _Collector()
    # compile() dá SyntaxError mais preciso que o pyflakes em alguns casos
    try:
        compile(source, "notebook.py", "exec")
    except SyntaxError as exc:
        collector.syntaxError("notebook.py", exc.msg or "syntax error", exc.lineno or 1,
                              exc.offset, exc.text)
        return collector.items  # pyflakes não roda com sintaxe quebrada
    with contextlib.suppress(Exception):  # pyflakes nunca deve derrubar a rota
        pyflakes_api.check(source, "notebook.py", collector)
    return collector.items
