import sqlite3
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from xsmb.storage import write_csv, write_parquet, write_sqlite
from xsmb.types import Draw


def _sample_draws() -> list[Draw]:
    return [
        Draw(
            date=date(2026, 5, 2),
            special="16132",
            prize1="71757",
            prize2=["99083", "98654"],
            prize3=["86938", "71437", "36884", "49158", "15991", "74525"],
            prize4=["3100", "7714", "4382", "0524"],
            prize5=["6046", "7173", "3104", "6621", "0697", "8307"],
            prize6=["960", "157", "907"],
            prize7=["41", "14", "62", "87"],
        ),
        Draw(
            date=date(2026, 5, 1),
            special="96637",
            prize1="93296",
            prize2=["12155", "58409"],
            prize3=["22927", "29764", "94519", "63942", "21062", "69625"],
            prize4=["0114", "2932", "0581", "7691"],
            prize5=["5151", "1059", "8554", "7671", "0982", "0427"],
            prize6=["355", "722", "435"],
            prize7=["48", "39", "79", "46"],
        ),
    ]


def test_write_csv_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "xsmb.csv"
    n = write_csv(_sample_draws(), path)
    assert n == 2
    lines = path.read_text().strip().split("\n")
    assert lines[0].startswith("date,special,prize1,prize2_1")
    assert lines[1].startswith("2026-05-01")  # sorted ascending
    assert lines[2].startswith("2026-05-02")


def test_write_sqlite_creates_both_tables(tmp_path: Path) -> None:
    path = tmp_path / "xsmb.sqlite"
    write_sqlite(_sample_draws(), path)
    conn = sqlite3.connect(path)
    try:
        draws_count = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        numbers_count = conn.execute("SELECT COUNT(*) FROM numbers").fetchone()[0]
        last2_indexed = conn.execute("SELECT COUNT(*) FROM numbers WHERE last2 = '32'").fetchone()[
            0
        ]
    finally:
        conn.close()
    assert draws_count == 2
    assert numbers_count == 2 * 27
    assert last2_indexed >= 1  # special 16132 → last2 = 32


def test_write_parquet_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "xsmb.parquet"
    write_parquet(_sample_draws(), path)
    table = pq.read_table(path)
    assert table.num_rows == 2
    assert "prize7_4" in table.column_names
