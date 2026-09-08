"""Geração de dados sintéticos para testes de engenharia de dados.

Usado pelo endpoint `POST /api/workspaces/{id}/generate` para materializar
arquivos grandes (ex.: CSV de 1.000.000 de linhas) direto no filesystem do
Workspace, sem passar pelo navegador nem carregar tudo em memória.
"""

from __future__ import annotations

import datetime as _dt
import random
from collections.abc import Iterator

# Ordem fixa — o header e cada linha seguem exatamente esta sequência.
BI_CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "customer_id",
    "product_id",
    "date",
    "quantity",
    "price",
    "total",
    "region",
)

_REGIONS: tuple[str, ...] = ("Sudeste", "Sul", "Nordeste", "Norte", "Centro-Oeste")
_BASE_DATE = _dt.date(2026, 1, 1)
_DATE_SPAN_DAYS = 364


def iter_bi_csv_lines(rows: int, *, seed: int | None = None) -> Iterator[str]:
    """Gera as linhas de um CSV de vendas sintético (header + `rows` registros).

    Cada linha já vem com `\\n` no fim. Determinístico para um dado `seed`.
    `total` é sempre `quantity * price` (consistência para os testes de
    transformação de BI).
    """
    if rows < 1:
        raise ValueError("rows deve ser >= 1")

    rng = random.Random(seed if seed is not None else rows)
    yield ",".join(BI_CSV_COLUMNS) + "\n"

    for i in range(1, rows + 1):
        customer_id = 1000 + rng.randint(0, 4999)
        product_id = 500 + rng.randint(0, 999)
        day_offset = rng.randint(0, _DATE_SPAN_DAYS)
        date = (_BASE_DATE + _dt.timedelta(days=day_offset)).isoformat()
        quantity = rng.randint(1, 20)
        price = round(rng.uniform(5.0, 500.0), 2)
        total = round(quantity * price, 2)
        region = rng.choice(_REGIONS)
        yield (
            f"{i},{customer_id},{product_id},{date},"
            f"{quantity},{price:.2f},{total:.2f},{region}\n"
        )


def estimate_bi_csv_bytes(rows: int) -> int:
    """Estimativa grosseira do tamanho final (para checagem de limite)."""
    # ~52 bytes/linha em média + header.
    return len(",".join(BI_CSV_COLUMNS)) + 1 + rows * 52
