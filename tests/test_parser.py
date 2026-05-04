from datetime import date
from pathlib import Path

import pytest

from xsmb.parser import parse_page
from xsmb.types import PRIZE_SHAPE

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture, expected_top_date",
    [
        ("01-03-2005.html", date(2005, 3, 1)),
        ("15-06-2010.html", date(2010, 6, 15)),
        ("20-12-2015.html", date(2015, 12, 20)),
        ("10-08-2020.html", date(2020, 8, 10)),
        ("02-05-2026.html", date(2026, 5, 2)),
    ],
)
def test_parses_seven_consecutive_days(fixture: str, expected_top_date: date) -> None:
    html = (FIXTURES / fixture).read_text()
    draws = parse_page(html)

    assert len(draws) == 7, f"{fixture}: expected 7 boxes, got {len(draws)}"
    assert draws[0].date == expected_top_date

    dates = [d.date for d in draws]
    assert dates == sorted(dates, reverse=True), "boxes must be newest → oldest"
    for prev, curr in zip(dates, dates[1:], strict=False):
        assert (prev - curr).days == 1, f"non-consecutive days: {prev} → {curr}"


@pytest.mark.parametrize(
    "fixture",
    [f"{d}.html" for d in ("01-03-2005", "15-06-2010", "20-12-2015", "10-08-2020", "02-05-2026")],
)
def test_each_draw_has_complete_prize_shape(fixture: str) -> None:
    html = (FIXTURES / fixture).read_text()
    for draw in parse_page(html):
        for prize, (count, width) in PRIZE_SHAPE.items():
            value = getattr(draw, prize)
            items = [value] if isinstance(value, str) else value
            assert len(items) == count, f"{draw.date} {prize}: {len(items)} != {count}"
            for n in items:
                assert len(n) == width and n.isdigit(), f"{draw.date} {prize}: bad {n!r}"


def test_known_values_2026_05_02() -> None:
    html = (FIXTURES / "02-05-2026.html").read_text()
    draws = {d.date: d for d in parse_page(html)}
    d = draws[date(2026, 5, 2)]
    assert d.special == "16132"
    assert d.prize1 == "71757"
    assert d.prize2 == ["99083", "98654"]
    assert d.prize7 == ["41", "14", "62", "87"]


def test_to_row_has_28_columns() -> None:
    html = (FIXTURES / "02-05-2026.html").read_text()
    row = parse_page(html)[0].to_row()
    assert len(row) == 28
    assert row["date"] == "2026-05-02"
