"""Classificação de erro: TRANSIENT / PERMANENT / UNKNOWN.

Decide se um retry tem chance de sucesso. Regras conservadoras: na dúvida, UNKNOWN.
"""

from __future__ import annotations

from nbplatform.domain.enums import ErrorClass

# Códigos de erro internos (setados pelo worker) → classe.
_CODE_MAP: dict[str, ErrorClass] = {
    "LEASE_EXPIRED": ErrorClass.TRANSIENT,  # worker morreu; outro worker deve conseguir
    "TIMEOUT": ErrorClass.PERMANENT,  # re-rodar provavelmente estoura de novo
    "NOTEBOOK_ERROR": ErrorClass.UNKNOWN,  # refinado pela mensagem abaixo
    "WORKER_ERROR": ErrorClass.UNKNOWN,
}

# Nomes de exceção / trechos que indicam erro do código do usuário (não adianta repetir).
_PERMANENT_MARKERS = (
    "SyntaxError",
    "IndentationError",
    "NameError",
    "ImportError",
    "ModuleNotFoundError",
    "AttributeError",
    "TypeError",
    "KeyError",
    "IndexError",
    "ValueError",
    "AssertionError",
    "RuntimeError",
    "RecursionError",
    "PermissionError",
    "FileNotFoundError",
    "NotImplementedError",
    "ZeroDivisionError",
    "authentication failed",
    "invalid credentials",
    "permission denied",
    "syntax error at or near",  # SQL inválido
)

# Trechos que indicam infra instável (retry pode resolver).
_TRANSIENT_MARKERS = (
    "ConnectionError",
    "ConnectionResetError",
    "ConnectionRefusedError",
    "TimeoutError",
    "timed out",
    "connection timeout",
    "temporarily unavailable",
    "ServerDisconnected",
    "OperationalError",  # SQLAlchemy: normalmente indisponibilidade
    "could not connect",
    "Connection refused",
    "Redis",
    " 429",
    " 502",
    " 503",
    " 504",
    "Too Many Requests",
    "Bad Gateway",
    "Service Unavailable",
    "Gateway Timeout",
)


def classify(error_code: str | None, error_message: str | None) -> ErrorClass:
    message = error_message or ""

    if error_code in _CODE_MAP:
        base = _CODE_MAP[error_code]
        if base is not ErrorClass.UNKNOWN:
            return base

    for marker in _TRANSIENT_MARKERS:
        if marker in message:
            return ErrorClass.TRANSIENT

    for marker in _PERMANENT_MARKERS:
        if marker in message:
            return ErrorClass.PERMANENT

    return ErrorClass.UNKNOWN
