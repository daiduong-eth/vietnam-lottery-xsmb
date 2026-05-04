"""HTML parser for Minh Ngọc XSMB result pages.

Each page returns up to 7 boxes (the requested date + 6 prior days). The actual
draw date is read from each box title (`KẾT QUẢ XỔ SỐ Miền Bắc-DD/MM/YYYY`),
which allows us to detect fallback pages where the site serves a different date
than requested.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from selectolax.parser import HTMLParser, Node

from xsmb.types import PRIZE_SHAPE, Draw

_TITLE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _box_date(box: Node) -> date | None:
    title = box.css_first(".box_kqxs_title, .title, h2, h3")
    if title is None:
        return None
    match = _TITLE_RE.search(title.text(strip=True))
    if match is None:
        return None
    return datetime.strptime(match.group(0), "%d/%m/%Y").date()


def _box_prizes(box: Node) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for prize in PRIZE_SHAPE:
        cell = box.css_first(
            f".{'giaidb' if prize == 'special' else prize.replace('prize', 'giai')}"
        )
        if cell is None:
            out[prize] = []
            continue
        nums = [d.text(strip=True) for d in cell.css("div") if d.text(strip=True)]
        if not nums:
            text = cell.text(strip=True)
            width = PRIZE_SHAPE[prize][1]
            nums = [text[i : i + width] for i in range(0, len(text), width)] if text else []
        out[prize] = nums
    return out


def _build_draw(draw_date: date, prizes: dict[str, list[str]]) -> Draw | None:
    if not prizes.get("special") or not prizes.get("prize1"):
        return None
    try:
        draw = Draw(
            date=draw_date,
            special=prizes["special"][0],
            prize1=prizes["prize1"][0],
            prize2=prizes.get("prize2", []),
            prize3=prizes.get("prize3", []),
            prize4=prizes.get("prize4", []),
            prize5=prizes.get("prize5", []),
            prize6=prizes.get("prize6", []),
            prize7=prizes.get("prize7", []),
        )
        draw.validate()
    except (ValueError, IndexError):
        return None
    return draw


def parse_page(html: str) -> list[Draw]:
    """Return every valid draw found in a Minh Ngọc results page."""
    tree = HTMLParser(html)
    draws: list[Draw] = []
    seen: set[date] = set()
    for box in tree.css(".box_kqxs"):
        draw_date = _box_date(box)
        if draw_date is None or draw_date in seen:
            continue
        draw = _build_draw(draw_date, _box_prizes(box))
        if draw is not None:
            draws.append(draw)
            seen.add(draw_date)
    return draws
