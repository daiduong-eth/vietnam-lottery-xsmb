"""Statistics over XSMB special-prize history.

All functions take an open `sqlite3.Connection` (built via `xsmb build-db`)
and return plain dicts/lists — no rendering. Keeps this module pure and
testable without touching the file system.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date

from xsmb.types import PRIZE_SHAPE


@dataclass(slots=True)
class SpecialPoint:
    date: date
    special: str

    @property
    def last2(self) -> str:
        return self.special[-2:]

    @property
    def chuc(self) -> int:
        return int(self.last2[0])

    @property
    def dv(self) -> int:
        return int(self.last2[1])


def load_specials(conn: sqlite3.Connection) -> list[SpecialPoint]:
    """All special results sorted ascending by date."""
    rows = conn.execute("SELECT date, special FROM draws ORDER BY date").fetchall()
    return [SpecialPoint(date.fromisoformat(d), s) for d, s in rows]


def latest_draw(conn: sqlite3.Connection) -> dict:
    """Return the most recent draw with all 27 numbers grouped by prize."""
    cursor = conn.execute("SELECT * FROM draws ORDER BY date DESC LIMIT 1")
    cols = [c[0] for c in cursor.description]
    row = dict(zip(cols, cursor.fetchone(), strict=True))
    out: dict = {
        "date": date.fromisoformat(row["date"]),
        "special": row["special"],
        "prize1": row["prize1"],
    }
    for prize in ("prize2", "prize3", "prize4", "prize5", "prize6", "prize7"):
        out[prize] = [row[f"{prize}_{i}"] for i in range(1, PRIZE_SHAPE[prize][0] + 1)]
    return out


def recent_table(conn: sqlite3.Connection, n: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT date, special FROM draws ORDER BY date DESC LIMIT ?", (n,)
    ).fetchall()
    out: list[dict] = []
    for d_str, special in rows:
        last2 = special[-2:]
        chuc, dv = int(last2[0]), int(last2[1])
        out.append(
            {
                "date": date.fromisoformat(d_str),
                "special": special,
                "last2": last2,
                "sum": chuc + dv,
                "chuc_parity": "C" if chuc % 2 == 0 else "L",
                "dv_parity": "C" if dv % 2 == 0 else "L",
                "chuc_size": "L" if chuc >= 5 else "B",
                "dv_size": "L" if dv >= 5 else "B",
            }
        )
    return out


def hot_cold(specials: list[SpecialPoint], top: int = 5) -> dict[str, dict]:
    """Hot/cold last-2 numbers across rolling windows + all-time."""
    today = specials[-1].date
    windows: list[tuple[str, list[SpecialPoint]]] = [
        ("30d", [p for p in specials if (today - p.date).days < 30]),
        ("90d", [p for p in specials if (today - p.date).days < 90]),
        ("365d", [p for p in specials if (today - p.date).days < 365]),
        ("all_time", specials),
    ]
    out: dict[str, dict] = {}
    for label, window in windows:
        counter: Counter[str] = Counter(p.last2 for p in window)
        for n in range(100):
            counter.setdefault(f"{n:02d}", 0)
        items = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
        out[label] = {
            "n_draws": len(window),
            "hot": items[:top],
            "cold": sorted(counter.items(), key=lambda x: (x[1], x[0]))[:top],
        }
    return out


def lo_gan(specials: list[SpecialPoint], top: int = 10) -> list[dict]:
    """Numbers (00–99) longest absent as ĐB last-2 ranked by gan days."""
    today = specials[-1].date
    last_seen: dict[str, date] = {}
    for p in specials:
        last_seen[p.last2] = p.date
    rows: list[dict] = []
    for n in range(100):
        ns = f"{n:02d}"
        last = last_seen.get(ns)
        if last is None:
            rows.append({"number": ns, "last_seen": None, "days": (today - specials[0].date).days})
        else:
            rows.append({"number": ns, "last_seen": last, "days": (today - last).days})
    rows.sort(key=lambda r: -r["days"])
    return rows[:top]


_STREAK_KEYS: list[tuple[str, str, callable]] = [
    ("dv_even", "Đơn vị **chẵn** liên tiếp", lambda p: p.dv % 2 == 0),
    ("dv_odd", "Đơn vị **lẻ** liên tiếp", lambda p: p.dv % 2 == 1),
    ("chuc_even", "Hàng chục **chẵn** liên tiếp", lambda p: p.chuc % 2 == 0),
    ("chuc_odd", "Hàng chục **lẻ** liên tiếp", lambda p: p.chuc % 2 == 1),
    ("dv_big", "Đơn vị **lớn** (≥5) liên tiếp", lambda p: p.dv >= 5),
    ("dv_small", "Đơn vị **bé** (<5) liên tiếp", lambda p: p.dv < 5),
    ("chuc_big", "Hàng chục **lớn** (≥5) liên tiếp", lambda p: p.chuc >= 5),
    ("chuc_small", "Hàng chục **bé** (<5) liên tiếp", lambda p: p.chuc < 5),
    ("sum_even", "Tổng (đv+chục) **chẵn**", lambda p: (p.dv + p.chuc) % 2 == 0),
    ("sum_odd", "Tổng (đv+chục) **lẻ**", lambda p: (p.dv + p.chuc) % 2 == 1),
    ("kep", "Số **kép** (đv = chục, VD 22, 88)", lambda p: p.dv == p.chuc),
]


def streaks(specials: list[SpecialPoint]) -> list[dict]:
    """Current-trailing + longest-ever streak for each parity classification."""
    out: list[dict] = []
    for _key, label, predicate in _STREAK_KEYS:
        flags = [predicate(p) for p in specials]

        current = 0
        for f in reversed(flags):
            if f:
                current += 1
            else:
                break

        max_len = 0
        max_start: date | None = None
        max_end: date | None = None
        run_start: date | None = None
        run_len = 0
        for p, f in zip(specials, flags, strict=True):
            if f:
                if run_len == 0:
                    run_start = p.date
                run_len += 1
                if run_len > max_len:
                    max_len = run_len
                    max_start = run_start
                    max_end = p.date
            else:
                run_len = 0

        out.append(
            {
                "label": label,
                "current": current,
                "max": max_len,
                "max_start": max_start,
                "max_end": max_end,
            }
        )
    return out


_ALTERNATING_KEYS: list[tuple[str, str, callable]] = [
    ("alt_dv_parity", "Đơn vị **chẵn ↔ lẻ**", lambda p: p.dv % 2 == 0),
    ("alt_chuc_parity", "Hàng chục **chẵn ↔ lẻ**", lambda p: p.chuc % 2 == 0),
    ("alt_sum_parity", "Tổng (đv+chục) **chẵn ↔ lẻ**", lambda p: (p.dv + p.chuc) % 2 == 0),
    ("alt_dv_size", "Đơn vị **lớn ↔ bé**", lambda p: p.dv >= 5),
    ("alt_chuc_size", "Hàng chục **lớn ↔ bé**", lambda p: p.chuc >= 5),
]


def alternating_streaks(specials: list[SpecialPoint]) -> list[dict]:
    """Longest run where consecutive draws flip the predicate value (so le)."""
    out: list[dict] = []
    for _key, label, predicate in _ALTERNATING_KEYS:
        flags = [predicate(p) for p in specials]

        max_len = 1
        max_start: date = specials[0].date
        max_end: date = specials[0].date
        run_len = 1
        run_start: date = specials[0].date
        for i in range(1, len(flags)):
            if flags[i] != flags[i - 1]:
                run_len += 1
                if run_len > max_len:
                    max_len = run_len
                    max_start = run_start
                    max_end = specials[i].date
            else:
                run_len = 1
                run_start = specials[i].date

        current = 1
        for i in range(len(flags) - 1, 0, -1):
            if flags[i] != flags[i - 1]:
                current += 1
            else:
                break

        out.append(
            {
                "label": label,
                "current": current,
                "max": max_len,
                "max_start": max_start,
                "max_end": max_end,
            }
        )
    return out


def heatmap(specials: list[SpecialPoint]) -> list[list[int]]:
    """10×10 grid of ĐB last-2 counts. grid[chục][đv] = count."""
    grid = [[0] * 10 for _ in range(10)]
    for p in specials:
        grid[p.chuc][p.dv] += 1
    return grid


def yearly_summary(specials: list[SpecialPoint]) -> list[dict]:
    """Per-year: # draws, # distinct last-2, top last-2."""
    by_year: dict[int, list[SpecialPoint]] = {}
    for p in specials:
        by_year.setdefault(p.date.year, []).append(p)
    out: list[dict] = []
    for year in sorted(by_year):
        bucket = by_year[year]
        counts = Counter(p.last2 for p in bucket)
        top, top_n = max(counts.items(), key=lambda x: (x[1], -int(x[0])))
        out.append(
            {
                "year": year,
                "draws": len(bucket),
                "distinct_last2": len(counts),
                "top_last2": top,
                "top_count": top_n,
            }
        )
    return out
