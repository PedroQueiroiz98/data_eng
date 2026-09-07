from __future__ import annotations

from nbplatform.core.masking import is_sensitive_key, mask_params, mask_secrets


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


def test_is_sensitive_key() -> None:
    for name in ("password", "SENHA", "api_key", "apiKey", "db_token", "connection_string"):
        assert is_sensitive_key(name)
    for name in ("date", "environment", "customer_id", "limit"):
        assert not is_sensitive_key(name)


def test_mask_params_only_masks_sensitive_keys() -> None:
    out = mask_params({"date": "2026-09-07", "customer_id": 123, "api_key": "xyz", "senha": "p"})
    assert out == {
        "date": "2026-09-07",
        "customer_id": 123,
        "api_key": "********",
        "senha": "********",
    }
