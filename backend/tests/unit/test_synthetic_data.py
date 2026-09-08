from __future__ import annotations

import pytest

from nbplatform.domain.synthetic_data import BI_CSV_COLUMNS, iter_bi_csv_lines


def test_header_and_row_count() -> None:
    lines = list(iter_bi_csv_lines(1000, seed=1))
    assert lines[0].rstrip("\n") == ",".join(BI_CSV_COLUMNS)
    assert len(lines) == 1001  # header + 1000
    assert all(line.endswith("\n") for line in lines)


def test_columns_and_total_consistency() -> None:
    for line in list(iter_bi_csv_lines(500, seed=42))[1:]:
        cells = line.rstrip("\n").split(",")
        assert len(cells) == len(BI_CSV_COLUMNS)
        _id, _cust, _prod, _date, qty, price, total, region = cells
        assert round(float(qty) * float(price), 2) == float(total)
        assert region in {"Sudeste", "Sul", "Nordeste", "Norte", "Centro-Oeste"}


def test_deterministic_for_seed() -> None:
    a = list(iter_bi_csv_lines(200, seed=99))
    b = list(iter_bi_csv_lines(200, seed=99))
    c = list(iter_bi_csv_lines(200, seed=100))
    assert a == b
    assert a != c


def test_sequential_ids() -> None:
    rows = list(iter_bi_csv_lines(50, seed=3))[1:]
    ids = [int(r.split(",", 1)[0]) for r in rows]
    assert ids == list(range(1, 51))


def test_rejects_zero_rows() -> None:
    with pytest.raises(ValueError):
        list(iter_bi_csv_lines(0))
