from __future__ import annotations

from nbplatform.core.masking import mask_secrets


def test_masks_secret_values() -> None:
    text = "conectando com token=abcd1234efgh e senha=SuperSecret99"
    out = mask_secrets(text, ["abcd1234efgh", "SuperSecret99"])
    assert "abcd1234efgh" not in out
    assert "SuperSecret99" not in out
    assert out.count("***") == 2


def test_ignores_short_and_empty_values() -> None:
    text = "x=ab e y="
    assert mask_secrets(text, ["ab", "", "abc"]) == text  # < 4 chars


def test_no_secrets_is_identity() -> None:
    assert mask_secrets("nada aqui", []) == "nada aqui"
