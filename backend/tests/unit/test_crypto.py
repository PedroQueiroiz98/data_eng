from __future__ import annotations

import pytest

from nbplatform.core.crypto import SecretCipher


def test_roundtrip() -> None:
    cipher = SecretCipher(SecretCipher.generate_key())
    token = cipher.encrypt("s3nha-do-banco")
    assert token != "s3nha-do-banco"
    assert cipher.decrypt(token) == "s3nha-do-banco"


def test_wrong_key_cannot_decrypt() -> None:
    a = SecretCipher(SecretCipher.generate_key())
    b = SecretCipher(SecretCipher.generate_key())
    token = a.encrypt("x")
    with pytest.raises(ValueError):
        b.decrypt(token)


def test_invalid_key_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError):
        SecretCipher("not-a-valid-fernet-key")
