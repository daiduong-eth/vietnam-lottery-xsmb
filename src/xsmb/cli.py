"""Command-line entrypoints for backfill and daily update."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import click

from xsmb.backfill import EARLIEST_KNOWN, crawl_range
from xsmb.storage import write_csv, write_parquet, write_sqlite
from xsmb.types import Draw


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _persist(draws: list[Draw], data_dir: Path) -> None:
    n = write_csv(draws, data_dir / "xsmb.csv")
    write_parquet(draws, data_dir / "xsmb.parquet")
    click.echo(f"wrote {n} draws → {data_dir / 'xsmb.csv'}, {data_dir / 'xsmb.parquet'}")


@click.group()
def main() -> None:
    """XSMB lottery dataset CLI."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr
    )


@main.command()
@click.option("--start", default=EARLIEST_KNOWN.isoformat(), help="YYYY-MM-DD")
@click.option("--end", default=None, help="YYYY-MM-DD (default: today)")
@click.option("--data-dir", default="data", type=click.Path(path_type=Path))
@click.option("--concurrency", default=4, type=int)
@click.option("--min-interval", default=0.5, type=float, help="seconds between requests")
def backfill(
    start: str, end: str | None, data_dir: Path, concurrency: int, min_interval: float
) -> None:
    """Crawl the full date range from Minh Ngọc."""
    start_d = _parse_date(start)
    end_d = _parse_date(end) if end else date.today()

    last_log = [0]

    def progress(have: int, total: int) -> None:
        if have - last_log[0] >= 100 or have == total:
            click.echo(f"  {have}/{total} draws collected", err=True)
            last_log[0] = have

    draws = asyncio.run(
        crawl_range(
            start_d, end_d, concurrency=concurrency, min_interval=min_interval, progress=progress
        )
    )
    click.echo(f"collected {len(draws)} draws in [{start_d}, {end_d}]")
    _persist(draws, data_dir)


@main.command()
@click.option("--days", default=7, type=int, help="how many recent days to refresh")
@click.option("--data-dir", default="data", type=click.Path(path_type=Path))
def update(days: int, data_dir: Path) -> None:
    """Refresh the last N days (default 7) — for daily cron."""
    end_d = date.today()
    start_d = end_d - timedelta(days=days - 1)
    draws = asyncio.run(crawl_range(start_d, end_d, concurrency=2, min_interval=0.5))
    click.echo(f"fetched {len(draws)} recent draws")

    csv_path = data_dir / "xsmb.csv"
    merged = _merge_csv(csv_path, draws)
    _persist(merged, data_dir)


def _merge_csv(csv_path: Path, fresh: list[Draw]) -> list[Draw]:
    if not csv_path.exists():
        return fresh
    import csv as csv_mod

    fresh_by_date = {d.date: d for d in fresh}
    out: list[Draw] = []
    with csv_path.open() as f:
        for row in csv_mod.DictReader(f):
            d_date = _parse_date(row["date"])
            if d_date in fresh_by_date:
                continue
            out.append(_row_to_draw(row, d_date))
    out.extend(fresh_by_date.values())
    return out


def _row_to_draw(row: dict[str, str], d_date: date) -> Draw:
    from xsmb.types import PRIZE_SHAPE

    fields: dict = {"date": d_date, "special": row["special"], "prize1": row["prize1"]}
    for prize in ("prize2", "prize3", "prize4", "prize5", "prize6", "prize7"):
        count = PRIZE_SHAPE[prize][0]
        fields[prize] = [row[f"{prize}_{i}"] for i in range(1, count + 1)]
    return Draw(**fields)


@main.command("render-readme")
@click.option("--data-dir", default="data", type=click.Path(path_type=Path))
@click.option("--out", default="README.md", type=click.Path(path_type=Path))
def render_readme_cmd(data_dir: Path, out: Path) -> None:
    """Render README.md as a stats dashboard from data/xsmb.sqlite."""
    import sqlite3

    from xsmb.render import render_readme

    db = data_dir / "xsmb.sqlite"
    if not db.exists():
        raise click.ClickException(f"{db} not found — run `xsmb build-db` first")
    conn = sqlite3.connect(db)
    try:
        out.write_text(render_readme(conn))
    finally:
        conn.close()
    click.echo(f"wrote {out}")


@main.command("build-db")
@click.option("--data-dir", default="data", type=click.Path(path_type=Path))
def build_db(data_dir: Path) -> None:
    """Rebuild data/xsmb.sqlite from data/xsmb.csv (offline, ~1 second)."""
    import csv as csv_mod

    csv_path = data_dir / "xsmb.csv"
    if not csv_path.exists():
        raise click.ClickException(f"{csv_path} not found — run `xsmb backfill` first")
    draws: list[Draw] = []
    with csv_path.open() as f:
        for row in csv_mod.DictReader(f):
            draws.append(_row_to_draw(row, _parse_date(row["date"])))
    n = write_sqlite(draws, data_dir / "xsmb.sqlite")
    click.echo(f"built SQLite with {n} draws → {data_dir / 'xsmb.sqlite'}")


if __name__ == "__main__":
    main()
