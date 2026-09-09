from __future__ import annotations

from typing import Any

import pytest

from nbplatform.domain.assistant import AssistantTask
from nbplatform.services.assistant import context as ctx_mod
from nbplatform.services.assistant.context import build_context


@pytest.fixture(autouse=True)
def _no_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _empty(self: Any) -> dict[str, str]:
        return {}

    monkeypatch.setattr(
        "nbplatform.services.secret_service.SecretService.resolve_all", _empty
    )


async def test_imports_always_included_and_deduped() -> None:
    cells = [
        "import pandas as pd\nimport pandas as pd",
        "from pathlib import Path",
        "df = pd.DataFrame()\ndf.head()",
    ]
    ctx = await build_context(
        None,  # type: ignore[arg-type]
        cells=cells,
        active_index=2,
        cursor_line=None,
        cursor_col=None,
        task=AssistantTask.GENERATE,
    )
    assert "import pandas as pd" in ctx.imports
    assert "from pathlib import Path" in ctx.imports
    assert ctx.imports.count("import pandas as pd") == 1
    assert "df" in ctx.defined_names


async def test_sensitive_assignment_line_is_redacted() -> None:
    cells = [
        "api_key = 'sk-live-superlongsecretvalue1234567890'\nhost = 'db.local'",
        "print(host)",
    ]
    ctx = await build_context(
        None,  # type: ignore[arg-type]
        cells=cells,
        active_index=1,
        cursor_line=None,
        cursor_col=None,
        task=AssistantTask.EXPLAIN,
    )
    blob = ctx.current_cell + "\n".join(ctx.preceding_cells) + "\n".join(ctx.imports)
    assert "sk-live-superlongsecretvalue1234567890" not in blob
    assert "api_key" not in ctx.defined_names


async def test_mask_secrets_applied_to_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _secrets(self: Any) -> dict[str, str]:
        return {"DB_PASSWORD": "s3cr3t-token-value-xyz"}

    monkeypatch.setattr(
        "nbplatform.services.secret_service.SecretService.resolve_all", _secrets
    )
    ctx = await build_context(
        None,  # type: ignore[arg-type]
        cells=["df = 1"],
        active_index=0,
        cursor_line=None,
        cursor_col=None,
        task=AssistantTask.FIX,
        recent_error={
            "ename": "OperationalError",
            "evalue": "auth failed for s3cr3t-token-value-xyz",
            "traceback": ["line 1: connect(pw='s3cr3t-token-value-xyz')"],
        },
    )
    assert ctx.recent_error is not None
    assert "s3cr3t-token-value-xyz" not in ctx.recent_error


async def test_inline_splits_at_cursor() -> None:
    cell = "df = pd.read_csv('x.csv')\ndf['idade'] = "
    ctx = await build_context(
        None,  # type: ignore[arg-type]
        cells=[cell],
        active_index=0,
        cursor_line=1,
        cursor_col=len("df['idade'] = "),
        task=AssistantTask.INLINE,
    )
    assert ctx.cursor_prefix is not None
    assert ctx.cursor_prefix.rstrip().endswith("=")
    assert ctx.cursor_suffix == ""


async def test_budget_trims_preceding_cells_first() -> None:
    big = "x = " + ("1 + " * 400) + "1  # filler-relevant ="
    cells = [big, big, big, "import os", "result = 1"]
    ctx = await build_context(
        None,  # type: ignore[arg-type]
        cells=cells,
        active_index=4,
        cursor_line=None,
        cursor_col=None,
        task=AssistantTask.GENERATE,
        budget_chars=800,
    )
    assert "import os" in ctx.imports
    total = len(ctx.current_cell) + sum(len(p) for p in ctx.preceding_cells)
    assert total <= 1200  # margem: corte por prioridade


async def test_workspace_files_from_read_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    # sem user_id → não lê nada, mas não quebra
    ctx = await build_context(
        None,  # type: ignore[arg-type]
        cells=["import pandas as pd\npd.read_csv('data/clientes.csv')"],
        active_index=0,
        cursor_line=None,
        cursor_col=None,
        task=AssistantTask.GENERATE,
        user_id=None,
    )
    assert ctx.workspace_files == []
    assert ctx_mod._READ_PATH_RE.search("pd.read_csv('data/clientes.csv')")
