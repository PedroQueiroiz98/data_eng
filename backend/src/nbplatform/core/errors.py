"""Erros de domínio.

Os serviços levantam estes erros; um handler no FastAPI os traduz para HTTP.
As rotas não montam respostas de erro manualmente.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base de todos os erros de domínio."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class DomainValidationError(DomainError):
    status_code = 422
    code = "validation_error"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"
