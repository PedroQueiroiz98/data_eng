from __future__ import annotations

import pytest

from nbplatform.core.errors import DomainValidationError
from nbplatform.domain.notebook_format import (
    has_parameters_cell,
    new_empty_notebook,
    validate_notebook,
)


def test_new_empty_notebook_is_valid_v4_with_parameters_cell() -> None:
    nb = new_empty_notebook()
    assert nb["nbformat"] == 4
    assert isinstance(nb["cells"], list) and len(nb["cells"]) >= 1
    assert has_parameters_cell(nb) is True
    # deve passar pela própria validação sem erro
    validate_notebook(nb)


def test_validate_accepts_minimal_notebook() -> None:
    minimal = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": "# Olá"},
            {
                "cell_type": "code",
                "metadata": {},
                "source": "print(1)",
                "outputs": [],
                "execution_count": None,
            },
        ],
    }
    out = validate_notebook(minimal)
    assert out["cells"][0]["cell_type"] == "markdown"
    assert out["cells"][1]["cell_type"] == "code"


def test_validate_rejects_non_dict() -> None:
    with pytest.raises(DomainValidationError):
        validate_notebook("nope")


def test_validate_rejects_malformed_cells() -> None:
    bad = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [{"foo": 1}]}
    with pytest.raises(DomainValidationError):
        validate_notebook(bad)


def test_has_parameters_cell_false_when_untagged() -> None:
    code_cell = {
        "cell_type": "code",
        "metadata": {},
        "source": "x = 1",
        "outputs": [],
        "execution_count": None,
    }
    nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [code_cell]}
    assert has_parameters_cell(nb) is False
