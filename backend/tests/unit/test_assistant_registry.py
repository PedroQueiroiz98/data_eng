from __future__ import annotations

import pytest

from nbplatform.services.assistant.registry import UnknownProviderType, default_registry


def test_default_registry_has_all_three() -> None:
    reg = default_registry()
    assert set(reg.types()) == {"OPENAI", "AZURE_OPENAI", "OLLAMA"}
    assert reg.has("OPENAI")
    assert reg.get("OLLAMA").provider_type == "OLLAMA"


def test_unknown_type_raises() -> None:
    with pytest.raises(UnknownProviderType):
        default_registry().get("GEMINI")
