import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from xsmb.stats import (
    SpecialPoint,
    alternating_streaks,
    hot_cold,
    latest_draw,
    lo_gan,
    recent_table,
    streaks,
)
from xsmb.storage import write_sqlite
from xsmb.types import Draw


def _draw(d: date, special: str) -> Draw:
    return Draw(
        date=d,
        special=special,
        prize1="00000",
        prize2=["00000", "00000"],
        prize3=["00000"] * 6,
        prize4=["0000"] * 4,
        prize5=["0000"] * 6,
        prize6=["000"] * 3,
        prize7=["00"] * 4,
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    # 5 days: 2020-01-01..05 with specials 11111, 22222, 11111, 33333, 44444
    draws = [
        _draw(date(2020, 1, 1), "11111"),
        _draw(date(2020, 1, 2), "22222"),
        _draw(date(2020, 1, 3), "11111"),
        _draw(date(2020, 1, 4), "33333"),
        _draw(date(2020, 1, 5), "44444"),
    ]
    db = tmp_path / "x.sqlite"
    write_sqlite(draws, db)
    return sqlite3.connect(db)


def test_latest_draw_picks_max_date(conn: sqlite3.Connection) -> None:
    d = latest_draw(conn)
    assert d["date"] == date(2020, 1, 5)
    assert d["special"] == "44444"
    assert len(d["prize7"]) == 4


def test_recent_table_orders_desc(conn: sqlite3.Connection) -> None:
    rows = recent_table(conn, n=3)
    assert [r["date"] for r in rows] == [date(2020, 1, 5), date(2020, 1, 4), date(2020, 1, 3)]
    assert rows[0]["last2"] == "44"
    assert rows[0]["sum"] == 8
    assert rows[0]["dv_parity"] == "C"
    assert rows[0]["chuc_parity"] == "C"
    # 4 < 5 → Bé both digits
    assert rows[0]["dv_size"] == "B"
    assert rows[0]["chuc_size"] == "B"


def test_lo_gan_ranks_oldest_first(conn: sqlite3.Connection) -> None:
    from xsmb.stats import load_specials

    rows = lo_gan(load_specials(conn), top=3)
    # Number "11" last appeared 2020-01-03 (gan = 2 days from 2020-01-05)
    # Number "44" last appeared 2020-01-05 (gan = 0)
    # Numbers never appearing: gan = (today - earliest) = 4 days
    top = rows[0]
    assert top["days"] >= 4  # never-appeared dominates
    assert top["last_seen"] is None


def test_streak_dv_even_long_run() -> None:
    # 6 consecutive even days then 1 odd
    base = date(2020, 1, 1)
    specs = [
        SpecialPoint(base + timedelta(days=i), f"000{n}")
        for i, n in enumerate(["12", "24", "36", "48", "60", "82", "11"])
    ]
    rows = streaks(specs)
    dv_even = next(r for r in rows if "Đơn vị **chẵn**" in r["label"])
    assert dv_even["max"] == 6
    assert dv_even["max_start"] == base
    assert dv_even["max_end"] == base + timedelta(days=5)
    assert dv_even["current"] == 0  # broken by last odd


def test_streak_dv_big_run() -> None:
    # 4 consecutive đv >=5 (5,6,7,9), then a small (2)
    base = date(2020, 1, 1)
    specs = [
        SpecialPoint(base + timedelta(days=i), f"000{n}")
        for i, n in enumerate(["15", "26", "37", "49", "12"])
    ]
    rows = streaks(specs)
    dv_big = next(r for r in rows if "Đơn vị **lớn**" in r["label"])
    assert dv_big["max"] == 4
    assert dv_big["max_start"] == base
    assert dv_big["max_end"] == base + timedelta(days=3)
    assert dv_big["current"] == 0  # broken by last small
    dv_small = next(r for r in rows if "Đơn vị **bé**" in r["label"])
    assert dv_small["current"] == 1
    assert dv_small["max"] >= 1


def test_streak_chuc_size_threshold() -> None:
    # chục: 5 (Lớn), 6 (Lớn), 4 (Bé), 9 (Lớn)
    base = date(2020, 1, 1)
    specs = [
        SpecialPoint(base + timedelta(days=i), f"000{n}")
        for i, n in enumerate(["50", "61", "42", "93"])
    ]
    rows = streaks(specs)
    chuc_big = next(r for r in rows if "Hàng chục **lớn**" in r["label"])
    chuc_small = next(r for r in rows if "Hàng chục **bé**" in r["label"])
    assert chuc_big["max"] == 2  # 50, 61
    assert chuc_big["current"] == 1  # last 93
    assert chuc_small["max"] == 1
    assert chuc_small["current"] == 0


def test_streak_kep() -> None:
    # 22, 44, 88, 13 → kep streak = 3 then 0
    base = date(2020, 1, 1)
    specs = [
        SpecialPoint(base + timedelta(days=i), f"000{n}")
        for i, n in enumerate(["22", "44", "88", "13"])
    ]
    rows = streaks(specs)
    kep = next(r for r in rows if "kép" in r["label"])
    assert kep["max"] == 3
    assert kep["current"] == 0


def test_alternating_dv_parity() -> None:
    # đv: 2(C), 3(L), 4(C), 5(L), 7(L) → so le 4 vòng (2-3-4-5), bị phá ở vị trí 5
    base = date(2020, 1, 1)
    specs = [
        SpecialPoint(base + timedelta(days=i), f"000{n}")
        for i, n in enumerate(["12", "13", "14", "15", "17"])
    ]
    rows = alternating_streaks(specs)
    alt_dv = next(r for r in rows if "Đơn vị **chẵn ↔ lẻ**" in r["label"])
    assert alt_dv["max"] == 4
    assert alt_dv["max_start"] == base
    assert alt_dv["max_end"] == base + timedelta(days=3)
    # current trailing: last 2 đều lẻ → so le = 1
    assert alt_dv["current"] == 1


def test_alternating_keeps_running() -> None:
    # 5 kỳ luân phiên hoàn hảo C-L-C-L-C → max=5, current=5
    base = date(2020, 1, 1)
    specs = [
        SpecialPoint(base + timedelta(days=i), f"000{n}")
        for i, n in enumerate(["10", "21", "32", "43", "54"])
    ]
    rows = alternating_streaks(specs)
    alt_dv = next(r for r in rows if "Đơn vị **chẵn ↔ lẻ**" in r["label"])
    assert alt_dv["max"] == 5
    assert alt_dv["current"] == 5


def test_hot_cold_includes_all_100_numbers() -> None:
    base = date(2020, 1, 1)
    specs = [SpecialPoint(base + timedelta(days=i), f"000{i:02d}") for i in range(50)]
    data = hot_cold(specs, top=5)
    assert data["all_time"]["n_draws"] == 50
    # cold should include zeros for 50 unseen numbers
    cold = data["all_time"]["cold"]
    assert all(c[1] == 0 for c in cold)
