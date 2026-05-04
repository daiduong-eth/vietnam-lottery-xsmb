# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Cascade từ `/home/duongdd/CLAUDE.md` (portfolio profile) và `~/.claude/rules/*` (code-style, testing, api-conventions, branch-workflow). Chỉ ghi điều **đặc thù cho repo `vietnam-lottery-xsmb`**.

---

## 1. Mô tả

Crawl + lưu trữ kết quả XSMB từ 2005-01-01 đến hôm nay. Dataset phục vụ phân tích thống kê.

- **Source:** Minh Ngọc (`/ket-qua-xo-so/mien-bac/DD-MM-YYYY.html`) — server-rendered HTML, mỗi page trả 7 box (ngày yêu cầu + 6 ngày trước).
- **Output:** `data/xsmb.{csv,sqlite,parquet}` (commit vào git, ~< 10MB tổng).
- **Daily refresh:** GitHub Action cron `35 11 * * *` UTC = 18:35 ICT.

## 2. Commands

```bash
uv sync                                 # install deps
uv run xsmb build-db                    # rebuild data/xsmb.sqlite từ CSV (~1s, gitignored)
uv run xsmb backfill                    # crawl all-time, ~10 min
uv run xsmb backfill --start 2020-01-01 # subset
uv run xsmb update --days 7             # refresh recent (cho cron)
uv run pytest                           # 15 tests, < 1s
uv run pytest tests/test_parser.py -v   # 1 file
uv run ruff check . && uv run black .   # lint + format
```

## 3. Architecture (cần đọc nhiều file mới hiểu)

**Data flow:**
```
Minh Ngọc HTML → parser.parse_page() → list[Draw]
                                          ↓
backfill.crawl_range()  ←── source.Fetcher (async, rate-limit)
                                          ↓
              storage.write_{csv,sqlite,parquet}() → data/
```

**Insight then phải biết khi làm việc với codebase này:**

1. **Mỗi page = 7 ngày**, không phải 1. `backfill._window_anchors()` step 7 ngày để giảm 7× số request. Parser xử lý cả 7 box, dedupe theo date thực tế lấy từ title của box.

2. **Date validation từ title, không từ URL.** Minh Ngọc fallback page placeholder cho ngày trước archive (~2005-01) — title sẽ khác request. Parser bỏ qua box có title mismatch tự nhiên (extract date từ title, không trust URL).

3. **Schema kép trong SQLite:** `draws` wide (1 row/ngày, 28 cột) cho lookup nhanh + `numbers` long (date, prize, position, number, last2) cho group-by thống kê. Cột `last2` index sẵn vì hầu hết phân tích XSMB xoay quanh 2 số cuối.

4. **`Draw` dataclass dùng `list` thay vì `tuple`** — không frozen vì storage layer cần ergonomic. Validation gọi explicit qua `.validate()`, không tự động trong `__post_init__` để tránh fail trong middle of parsing.

## 4. Project-local Claude config

```
.claude/
├── settings.json            # team permissions (rỗng)
├── settings.local.json      # cá nhân (gitignored)
├── commands/, rules/, skills/, agents/  # placeholder, override khi cần
```

Chi tiết override: xem `.claude/*/SKILL.md` của từng skill — mặc định cascade từ `~/.claude/`.
