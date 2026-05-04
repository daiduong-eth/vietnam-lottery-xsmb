"""Persist draws to CSV, SQLite (wide + long), and Parquet."""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterable
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from xsmb.types import CSV_COLUMNS, PRIZE_SHAPE, Draw

_SCHEMA_DRAWS = f"""
CREATE TABLE IF NOT EXISTS draws (
    {", ".join(f'{c} TEXT' for c in CSV_COLUMNS if c != 'date')},
    date TEXT PRIMARY KEY
);
"""

_SCHEMA_NUMBERS = """
CREATE TABLE IF NOT EXISTS numbers (
    date TEXT NOT NULL,
    prize TEXT NOT NULL,
    position INTEGER NOT NULL,
    number TEXT NOT NULL,
    last2 TEXT NOT NULL,
    PRIMARY KEY (date, prize, position),
    FOREIGN KEY (date) REFERENCES draws(date)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_numbers_last2 ON numbers(last2);
CREATE INDEX IF NOT EXISTS idx_numbers_prize ON numbers(prize);
CREATE INDEX IF NOT EXISTS idx_numbers_number ON numbers(number);
"""


def write_csv(draws: Iterable[Draw], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [d.to_row() for d in draws]
    rows.sort(key=lambda r: r["date"])
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_sqlite(draws: Iterable[Draw], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rows = [d.to_row() for d in draws]
    rows.sort(key=lambda r: r["date"])
    long_rows = list(_explode_to_long(draws))

    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA_DRAWS + _SCHEMA_NUMBERS)
        placeholders = ", ".join("?" for _ in CSV_COLUMNS)
        conn.executemany(
            f"INSERT INTO draws ({', '.join(CSV_COLUMNS)}) VALUES ({placeholders})",
            [tuple(r[c] for c in CSV_COLUMNS) for r in rows],
        )
        conn.executemany(
            "INSERT INTO numbers (date, prize, position, number, last2) VALUES (?, ?, ?, ?, ?)",
            long_rows,
        )
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()
    return len(rows)


def write_parquet(draws: Iterable[Draw], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [d.to_row() for d in draws]
    rows.sort(key=lambda r: r["date"])
    if not rows:
        return 0
    table = pa.Table.from_pylist(rows, schema=pa.schema([(c, pa.string()) for c in CSV_COLUMNS]))
    pq.write_table(table, path, compression="zstd")
    return len(rows)


def _explode_to_long(draws: Iterable[Draw]) -> Iterable[tuple[str, str, int, str, str]]:
    for d in draws:
        for prize in PRIZE_SHAPE:
            value = getattr(d, prize)
            items = [value] if isinstance(value, str) else value
            for pos, number in enumerate(items, start=1):
                yield (d.date.isoformat(), prize, pos, number, number[-2:].zfill(2))
