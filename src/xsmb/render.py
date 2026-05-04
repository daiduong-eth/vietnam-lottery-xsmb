"""Render stats dict → markdown sections for the README dashboard."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from xsmb.stats import (
    alternating_streaks,
    heatmap,
    hot_cold,
    latest_draw,
    lo_gan,
    load_specials,
    recent_table,
    streaks,
    yearly_summary,
)

_VN_DOW = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
_HEAT_GLYPHS = "·░▒▓█"
_ICT = ZoneInfo("Asia/Ho_Chi_Minh")
_REPO = "daiduong-eth/vietnam-lottery-xsmb"


def _shield(label: str, message: str, color: str) -> str:
    """shields.io static badge with safe URL escaping for arbitrary text."""
    return (
        "https://img.shields.io/static/v1"
        f"?label={quote_plus(label)}&message={quote_plus(message)}&color={color}"
    )


def render_readme(conn: sqlite3.Connection) -> str:
    specials = load_specials(conn)
    if not specials:
        return "# XSMB\n\n*No data yet.*\n"
    sections = [
        _header(specials),
        _section_latest(conn),
        _section_recent(conn, n=10),
        _section_hot_cold(specials),
        _section_lo_gan(specials),
        _section_streaks(specials),
        _section_alternating(specials),
        _section_heatmap(specials),
        _section_yearly(specials),
        _footer(specials),
    ]
    return "\n\n".join(sections) + "\n"


def _header(specials) -> str:
    last = specials[-1]
    dow = _VN_DOW[last.date.weekday()]
    badges = [
        f"![daily-update](https://github.com/{_REPO}/actions/workflows/daily-update.yml/badge.svg)",
        f"![draws]({_shield('draws', f'{len(specials):,}', 'blue')})",
        f"![range]({_shield('range', f'{specials[0].date} → {last.date}', 'green')})",
        f"![views](https://hits.sh/github.com/{_REPO}.svg?label=views&color=orange)",
        f"![license]({_shield('license', 'MIT', 'yellow')})",
    ]
    return (
        "# Xổ Số Miền Bắc — Dashboard\n\n"
        + " ".join(badges)
        + f"\n\n**Kết quả mới nhất:** {dow}, {last.date:%d/%m/%Y} "
        f"— Đặc biệt **`{last.special}`** (2 số cuối: `{last.last2}`)"
    )


def _section_latest(conn: sqlite3.Connection) -> str:
    d = latest_draw(conn)
    rows = [
        ("Đặc biệt", [d["special"]]),
        ("Giải nhất", [d["prize1"]]),
        ("Giải nhì", d["prize2"]),
        ("Giải ba", d["prize3"]),
        ("Giải tư", d["prize4"]),
        ("Giải năm", d["prize5"]),
        ("Giải sáu", d["prize6"]),
        ("Giải bảy", d["prize7"]),
    ]
    body = "\n".join(f"| {label} | {' '.join(f'`{n}`' for n in nums)} |" for label, nums in rows)
    return (
        f"## 🎯 Kết quả mới nhất — {d['date']:%d/%m/%Y}\n\n" "| Giải | Số |\n|---|---|\n" f"{body}"
    )


def _section_recent(conn: sqlite3.Connection, n: int = 10) -> str:
    rows = recent_table(conn, n=n)
    body_lines = [
        "| Ngày | Đặc biệt | 2 số cuối | Tổng | Chục C/L | ĐV C/L | Chục L/B | ĐV L/B |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        body_lines.append(
            f"| {r['date']:%d/%m/%Y} ({_VN_DOW[r['date'].weekday()]}) "
            f"| `{r['special']}` | **{r['last2']}** | {r['sum']} "
            f"| {r['chuc_parity']} | {r['dv_parity']} "
            f"| {r['chuc_size']} | {r['dv_size']} |"
        )
    return (
        f"## 📅 {n} kỳ gần nhất\n\n"
        "C = Chẵn, L (cột C/L) = Lẻ; L (cột L/B) = Lớn (≥5), B = Bé (<5).\n\n"
        + "\n".join(body_lines)
    )


def _section_hot_cold(specials) -> str:
    data = hot_cold(specials, top=5)
    head = "| Cửa sổ | # kỳ | Top 5 nóng | Top 5 lạnh |\n|---|---|---|---|"
    rows: list[str] = []
    for label, key in [
        ("30 ngày", "30d"),
        ("90 ngày", "90d"),
        ("365 ngày", "365d"),
        ("Toàn lịch sử", "all_time"),
    ]:
        d = data[key]
        hot = " ".join(f"`{n}`({c})" for n, c in d["hot"])
        cold = " ".join(f"`{n}`({c})" for n, c in d["cold"])
        rows.append(f"| {label} | {d['n_draws']:,} | {hot} | {cold} |")
    return (
        "## 🔥 Top số 2 cuối ĐB — nóng / lạnh\n\n"
        "Số nóng: ra nhiều nhất trong cửa sổ; số lạnh: ra ít nhất. Format: `số`(số lần).\n\n"
        f"{head}\n" + "\n".join(rows)
    )


def _section_lo_gan(specials) -> str:
    rows = lo_gan(specials, top=10)
    body = ["| # | Số | Lần cuối về (ĐB) | Số ngày gan |", "|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        last_seen = r["last_seen"]
        last_str = f"{last_seen:%d/%m/%Y}" if isinstance(last_seen, date) else "_chưa từng_"
        body.append(f"| {i} | **{r['number']}** | {last_str} | {r['days']:,} |")
    return "## 😴 Lô gan — top 10 lâu chưa về (theo 2 số cuối ĐB)\n\n" + "\n".join(body)


def _section_streaks(specials) -> str:
    rows = streaks(specials)
    body = [
        "| Loại | Streak hiện tại | Dài nhất | Khoảng dài nhất |",
        "|---|---|---|---|",
    ]
    for r in rows:
        rng = ""
        if r["max_start"] and r["max_end"]:
            rng = f"{r['max_start']:%d/%m/%Y} → {r['max_end']:%d/%m/%Y}"
        current = str(r["current"]) if r["current"] > 0 else "—"
        body.append(f"| {r['label']} | {current} | **{r['max']}** | {rng} |")
    return (
        "## 🔁 Streak chẵn/lẻ + lớn/bé liên tiếp\n\n"
        "Tính trên 2 số cuối Đặc biệt qua toàn bộ lịch sử. "
        "**Lớn** = chữ số ≥5, **Bé** = chữ số <5.\n\n" + "\n".join(body)
    )


def _section_alternating(specials) -> str:
    rows = alternating_streaks(specials)
    body = [
        "| Loại | So le hiện tại | Dài nhất | Khoảng dài nhất |",
        "|---|---|---|---|",
    ]
    for r in rows:
        rng = ""
        if r["max_start"] and r["max_end"]:
            rng = f"{r['max_start']:%d/%m/%Y} → {r['max_end']:%d/%m/%Y}"
        current = str(r["current"]) if r["current"] > 1 else "—"
        body.append(f"| {r['label']} | {current} | **{r['max']}** | {rng} |")
    return (
        "## 🔀 Streak so le liên tiếp\n\n"
        "Đếm chuỗi mà 2 kỳ liên tiếp **luôn đổi loại** (vd C–L–C–L hoặc L–B–L–B). "
        "Bị phá khi 2 kỳ liền nhau cùng loại.\n\n" + "\n".join(body)
    )


def _section_heatmap(specials) -> str:
    grid = heatmap(specials)
    flat = [c for row in grid for c in row]
    lo, hi = min(flat), max(flat)
    span = max(hi - lo, 1)

    def glyph(c: int) -> str:
        idx = min(int((c - lo) / span * (len(_HEAT_GLYPHS) - 1) + 0.5), len(_HEAT_GLYPHS) - 1)
        return _HEAT_GLYPHS[idx]

    header = "       " + "    ".join(str(d) for d in range(10))
    lines = [header]
    for r, row in enumerate(grid):
        cells = "  ".join(f"{c:3d}{glyph(c)}" for c in row)
        lines.append(f"  {r}    {cells}")
    block = "\n".join(lines)
    return (
        "## 🗺 Heatmap 100 số (00–99) — toàn lịch sử\n\n"
        "Hàng = chữ số hàng chục, cột = đơn vị. Số bên trái là đếm; ký hiệu bên phải biểu thị mật độ "
        f"(`{_HEAT_GLYPHS[0]}` = ít nhất {lo}, `{_HEAT_GLYPHS[-1]}` = nhiều nhất {hi}).\n\n"
        "```\n" + block + "\n```"
    )


def _section_yearly(specials) -> str:
    rows = yearly_summary(specials)
    body = ["| Năm | # kỳ | # số 2-cuối khác nhau | Số ra nhiều nhất |", "|---|---|---|---|"]
    for r in rows[-12:]:  # last 12 years
        body.append(
            f"| {r['year']} | {r['draws']} | {r['distinct_last2']}/100 "
            f"| `{r['top_last2']}` ({r['top_count']} lần) |"
        )
    return "## 📈 Tổng kết theo năm (12 năm gần nhất)\n\n" + "\n".join(body)


def _footer(specials) -> str:
    now = datetime.now(_ICT)
    return (
        "---\n\n"
        f"_Updated **{now:%Y-%m-%d %H:%M %Z}** — auto by [GitHub Action](.github/workflows/daily-update.yml)._  \n"
        f"_Dataset: [`data/xsmb.csv`](data/xsmb.csv) · {len(specials):,} kỳ · {specials[0].date} → {specials[-1].date}._  \n"
        "_Code, install, schema: see [`docs/USAGE.md`](docs/USAGE.md). License: [MIT](LICENSE)._  \n"
        "_Source data crawled from [Minh Ngọc](https://www.minhngoc.net.vn/ket-qua-xo-so/mien-bac.html)._"
    )
