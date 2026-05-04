# vietnam-lottery-xsmb — Usage

Bộ dữ liệu kết quả **Xổ số Miền Bắc (XSMB)** từ **2005-01-01** đến hôm nay, cập nhật mỗi tối qua GitHub Actions.

> Phục vụ phân tích thống kê / nghiên cứu. KHÔNG dùng để dự đoán & đánh bạc — kết quả xổ số là biến ngẫu nhiên độc lập.

## Dataset

| File | In repo | Mục đích |
|---|---|---|
| `data/xsmb.csv` | ✅ | Wide format, 28 cột — mở Excel/pandas trực tiếp |
| `data/xsmb.parquet` | ✅ | Nén zstd, tốt cho pandas/polars/duckdb |
| `data/xsmb.sqlite` | dựng local | 2 bảng (`draws` wide + `numbers` long) — `uv run xsmb build-db` (~1s) |

SQLite không commit vào git (binary diff phình history).

### Schema — bảng `draws` (1 hàng = 1 kỳ quay)

| Cột | Số lượng | Số chữ số | Giải |
|---|---|---|---|
| `date` | 1 | — | YYYY-MM-DD |
| `special` | 1 | 5 | Đặc biệt |
| `prize1` | 1 | 5 | Nhất |
| `prize2_1..2` | 2 | 5 | Nhì |
| `prize3_1..6` | 6 | 5 | Ba |
| `prize4_1..4` | 4 | 4 | Tư |
| `prize5_1..6` | 6 | 4 | Năm |
| `prize6_1..3` | 3 | 3 | Sáu |
| `prize7_1..4` | 4 | 2 | Bảy |

### Schema — bảng `numbers` (long format)

```
date TEXT, prize TEXT, position INTEGER, number TEXT, last2 TEXT
```

Index sẵn trên `last2`, `prize`, `number`.

## Cài & chạy

```bash
git clone https://github.com/daiduong-eth/vietnam-lottery-xsmb.git
cd vietnam-lottery-xsmb
uv sync

uv run xsmb build-db          # dựng SQLite từ CSV
uv run xsmb backfill          # crawl lại all-time (~10 phút)
uv run xsmb update --days 7   # refresh ngày gần đây
uv run xsmb render-readme     # render lại README dashboard
uv run pytest                 # tests
```

## Ví dụ phân tích

### Pandas

```python
import pandas as pd
df = pd.read_csv("https://raw.githubusercontent.com/daiduong-eth/vietnam-lottery-xsmb/main/data/xsmb.csv",
                 dtype=str, parse_dates=["date"])
df["last2_db"] = df["special"].str[-2:]
df.groupby("last2_db").size().sort_values(ascending=False).head(10)
```

### SQLite — top 2 số cuối Đặc biệt 10 năm gần đây

```sql
SELECT last2, COUNT(*) AS n
FROM numbers
WHERE prize = 'special' AND date >= date('now', '-10 years')
GROUP BY last2
ORDER BY n DESC
LIMIT 10;
```

### DuckDB trên Parquet

```sql
SELECT date, special FROM 'xsmb.parquet'
WHERE strftime(date, '%w') = '1';  -- thứ 2
```

Xem [`notebooks/01_eda.ipynb`](../notebooks/01_eda.ipynb) cho EDA đầy đủ.

## Cấu trúc code

```
src/xsmb/
├── types.py        # Draw dataclass + schema constants
├── parser.py       # HTML → list[Draw], dùng selectolax
├── source.py       # async HTTP client, rate-limit + retry
├── backfill.py     # crawl khoảng ngày, tận dụng 7 box/page
├── storage.py      # ghi CSV / SQLite / Parquet
├── stats.py        # tính toán cho dashboard (pure)
├── render.py       # markdown render từ stats
└── cli.py          # `xsmb backfill | update | build-db | render-readme`
```

## Nguồn

Crawl từ [Minh Ngọc](https://www.minhngoc.net.vn/ket-qua-xo-so/mien-bac.html) — kết quả xổ số là dữ liệu công khai, không có copyright.
