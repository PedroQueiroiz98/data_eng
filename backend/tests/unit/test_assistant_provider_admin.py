from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from nbplatform.core.errors import DomainValidationError
from nbplatform.domain.assistant import AssistantProviderType
from nbplatform.schemas.assistant import MASK
from nbplatform.services.assistant import provider_admin as pa
from nbplatform.services.assistant.registry import default_registry


@pytest.mark.parametrize(
    "value,keep",
    [(None, True), ("", True), (MASK, True), ("sk-new", False)],
)
def test_keep_secret(value: str | None, keep: bool) -> None:
    assert pa._keep_secret(value) is keep


def test_validate_rejects_missing_model() -> None:
    reg = default_registry()
    with pytest.raises(DomainValidationError):
        pa._validate(reg, AssistantProviderType.OPENAI, {}, has_secret=True)


def test_validate_rejects_missing_key() -> None:
    reg = default_registry()
    with pytest.raises(DomainValidationError):
        pa._validate(
            reg, AssistantProviderType.OPENAI, {"model": "m"}, has_secret=False
        )


def test_validate_ok_for_ollama_without_key() -> None:
    reg = default_registry()
    pa._validate(
        reg,
        AssistantProviderType.OLLAMA,
        {"base_url": "http://x", "model": "llama3"},
        has_secret=False,
    )


class _Row:
    id = uuid.uuid4()
    name = "p1"
    description = None
    provider_type = AssistantProviderType.OPENAI
    enabled = True
    is_default = True
    configuration_json = {"model": "gpt-4o-mini"}
    secret_ct = "cipher"
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    updated_at = datetime(2026, 1, 1, tzinfo=UTC)


def test_to_read_hides_key_and_shows_has_key() -> None:
    read = pa._to_read(_Row(), default_registry())
    assert read.has_key is True
    assert "secret" not in read.configuration
    assert read.summary  # resumo do provider
