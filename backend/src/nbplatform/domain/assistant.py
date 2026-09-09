"""Domínio do assistente de IA: tipos de provider, tarefas, contexto e resultado.

Sem IO — dataclasses e enums puros, consumidos por models, schemas e serviços.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


class AssistantProviderType(StrEnum):
    OPENAI = "OPENAI"
    AZURE_OPENAI = "AZURE_OPENAI"
    OLLAMA = "OLLAMA"


class AssistantTask(StrEnum):
    GENERATE = "GENERATE"
    EXPLAIN = "EXPLAIN"
    FIX = "FIX"
    OPTIMIZE = "OPTIMIZE"
    TESTS = "TESTS"
    CONTINUE = "CONTINUE"
    CONVERT = "CONVERT"
    DOCSTRING = "DOCSTRING"
    CHAT = "CHAT"
    INLINE = "INLINE"


Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class AssistantContext:
    """Contexto montado (e sanitizado) para a IA — ver spec §8/§9/§14."""

    language: str = "python"
    current_cell: str = ""
    cursor_prefix: str | None = None
    cursor_suffix: str | None = None
    preceding_cells: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    defined_names: list[str] = field(default_factory=list)
    recent_error: str | None = None
    workspace_files: list[str] = field(default_factory=list)
    selection: str | None = None


@dataclass(frozen=True)
class AssistantRequest:
    task: AssistantTask
    messages: list[ChatMessage]
    max_tokens: int
    temperature: float
    stop: list[str] | None = None
    stream: bool = False


@dataclass(frozen=True)
class AssistantResult:
    ok: bool
    text: str = ""
    finish_reason: str = ""
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    interaction_id: str | None = None

    @classmethod
    def success(
        cls,
        text: str,
        *,
        model: str = "",
        finish_reason: str = "",
        usage: dict[str, int] | None = None,
    ) -> AssistantResult:
        return cls(
            ok=True,
            text=text,
            model=model,
            finish_reason=finish_reason,
            usage=usage or {},
        )

    @classmethod
    def failure(cls, error: str) -> AssistantResult:
        return cls(ok=False, error=error)


def cursor_offset(code: str, line0: int, col0: int) -> int:
    """(linha 0-based, coluna 0-based) → offset absoluto no texto."""
    lines = code.split("\n")
    if not lines:
        return 0
    line0 = max(0, min(line0, len(lines) - 1))
    col0 = max(0, min(col0, len(lines[line0])))
    return sum(len(ln) + 1 for ln in lines[:line0]) + col0
