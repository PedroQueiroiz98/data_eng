from __future__ import annotations

import time

import jwt
import pytest

from nbplatform.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("s3nha-secreta")
    assert h != "s3nha-secreta"
    assert h.startswith("pbkdf2_sha256$")
    assert verify_password("s3nha-secreta", h) is True
    assert verify_password("errada", h) is False
    assert verify_password("qualquer", None) is False
    assert verify_password("qualquer", "formato$estranho") is False


def test_jwt_roundtrip_and_claims() -> None:
    token = create_access_token(subject="user-123", role="admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["exp"] > time.time()


def test_jwt_rejects_tampered_token() -> None:
    token = create_access_token(subject="u", role="member")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "outra-chave", algorithms=["HS256"])
