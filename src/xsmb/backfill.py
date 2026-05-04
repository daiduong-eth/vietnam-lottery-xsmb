"""Crawl XSMB results in 7-day windows.

Each Minh Ngọc page returns the requested date plus the 6 days before it. We
crawl in steps of 7 to amortise requests, parsing every box on every page.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from xsmb.parser import parse_page
from xsmb.source import Fetcher
from xsmb.types import Draw

log = logging.getLogger(__name__)

WINDOW_DAYS = 7
EARLIEST_KNOWN = date(2005, 1, 1)


async def crawl_range(
    start: date,
    end: date,
    *,
    concurrency: int = 4,
    min_interval: float = 0.5,
    progress: callable | None = None,
) -> list[Draw]:
    """Return every distinct draw with date in [start, end], newest first."""
    if start > end:
        raise ValueError(f"start {start} is after end {end}")

    anchors = _window_anchors(start, end)
    seen: dict[date, Draw] = {}

    async with Fetcher(concurrency=concurrency, min_interval=min_interval) as fetcher:

        async def fetch_one(anchor: date) -> list[Draw]:
            try:
                html = await fetcher.fetch(anchor)
            except Exception as exc:
                log.warning("fetch %s failed: %s", anchor, exc)
                return []
            return parse_page(html)

        for batch in _chunked(anchors, concurrency * 4):
            results = await asyncio.gather(*(fetch_one(a) for a in batch))
            for draws in results:
                for d in draws:
                    if start <= d.date <= end:
                        seen[d.date] = d
            if progress is not None:
                progress(len(seen), len(anchors) * WINDOW_DAYS)

    return sorted(seen.values(), key=lambda d: d.date, reverse=True)


def _window_anchors(start: date, end: date) -> list[date]:
    anchors: list[date] = []
    cursor = end
    while cursor >= start:
        anchors.append(cursor)
        cursor -= timedelta(days=WINDOW_DAYS)
    return anchors


def _chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
