"""Criptografia simétrica para secrets (usada a partir da Fase 8).

Isolada aqui para que o resto do código nunca manipule chave/algoritmo diretamente.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class SecretCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:  # pragma: no cover - erro de configuração
            raise RuntimeError(
                "SECRET_ENCRYPTION_KEY inválida: gere uma chave Fernet real "
                '(`python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"`).'
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Não foi possível decifrar o secret (token inválido).") from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()
