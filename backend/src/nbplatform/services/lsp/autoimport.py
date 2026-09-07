"""Sugestões de import (nunca aplicadas automaticamente).

Combina um mapa curado de nomes comuns com uma verificação, via Jedi, de que um
módulo de mesmo nome realmente existe no ambiente. O frontend só insere o import
após confirmação do usuário.
"""

from __future__ import annotations

from dataclasses import dataclass

import jedi  # type: ignore[import-untyped]

# nome exposto -> (statement, módulo de origem)
_CURATED: dict[str, tuple[str, str]] = {
    "pd": ("import pandas as pd", "pandas"),
    "np": ("import numpy as np", "numpy"),
    "plt": ("import matplotlib.pyplot as plt", "matplotlib"),
    "sns": ("import seaborn as sns", "seaborn"),
    "DataFrame": ("from pandas import DataFrame", "pandas"),
    "Series": ("from pandas import Series", "pandas"),
    "array": ("from numpy import array", "numpy"),
    "datetime": ("from datetime import datetime", "datetime"),
    "date": ("from datetime import date", "datetime"),
    "timedelta": ("from datetime import timedelta", "datetime"),
    "Path": ("from pathlib import Path", "pathlib"),
    "defaultdict": ("from collections import defaultdict", "collections"),
    "Counter": ("from collections import Counter", "collections"),
    "json": ("import json", "json"),
    "os": ("import os", "os"),
    "sys": ("import sys", "sys"),
    "re": ("import re", "re"),
    "math": ("import math", "math"),
    "psycopg": ("import psycopg", "psycopg"),
    "sqlalchemy": ("import sqlalchemy", "sqlalchemy"),
}


@dataclass(frozen=True)
class ImportSuggestion:
    label: str
    statement: str
    module: str


def suggest(name: str, env_path: str) -> list[ImportSuggestion]:
    if not name or not name.isidentifier():
        return []
    out: list[ImportSuggestion] = []
    seen: set[str] = set()

    curated = _CURATED.get(name)
    if curated:
        stmt, mod = curated
        out.append(ImportSuggestion(label=stmt, statement=stmt, module=mod))
        seen.add(stmt)

    # módulo de mesmo nome instalado no ambiente?
    try:
        env = jedi.create_environment(env_path, safe=False) if env_path else None
        comps = jedi.Script(code=f"import {name}", environment=env).complete(1, len(name) + 7)
        for c in comps:
            if c.name == name and c.type == "module":
                stmt = f"import {name}"
                if stmt not in seen:
                    out.append(ImportSuggestion(label=stmt, statement=stmt, module=name))
                    seen.add(stmt)
                break
    except Exception:  # noqa: BLE001
        pass

    return out
