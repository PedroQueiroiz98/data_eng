from __future__ import annotations

import pytest

from nbplatform.domain.enums import ErrorClass
from nbplatform.domain.error_classification import classify


@pytest.mark.parametrize(
    ("code", "message", "expected"),
    [
        ("LEASE_EXPIRED", "worker morreu", ErrorClass.TRANSIENT),
        ("TIMEOUT", "timeout após 1800s", ErrorClass.PERMANENT),
        ("NOTEBOOK_ERROR", "NameError: name 'x' is not defined", ErrorClass.PERMANENT),
        ("NOTEBOOK_ERROR", "SyntaxError: invalid syntax", ErrorClass.PERMANENT),
        ("NOTEBOOK_ERROR", "ModuleNotFoundError: No module named 'foo'", ErrorClass.PERMANENT),
        ("NOTEBOOK_ERROR", "OperationalError: could not connect to server", ErrorClass.TRANSIENT),
        ("NOTEBOOK_ERROR", "HTTPError: 503 Service Unavailable", ErrorClass.TRANSIENT),
        ("WORKER_ERROR", "algo estranho aconteceu", ErrorClass.UNKNOWN),
        (None, None, ErrorClass.UNKNOWN),
        ("NOTEBOOK_ERROR", "psycopg.OperationalError: connection timeout", ErrorClass.TRANSIENT),
        ("NOTEBOOK_ERROR", "PermissionError: [Errno 13] permission denied", ErrorClass.PERMANENT),
    ],
)
def test_classify(code: str | None, message: str | None, expected: ErrorClass) -> None:
    assert classify(code, message) is expected
