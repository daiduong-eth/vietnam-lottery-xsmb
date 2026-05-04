from dataclasses import dataclass, field
from datetime import date

PRIZE_SHAPE: dict[str, tuple[int, int]] = {
    "special": (1, 5),
    "prize1": (1, 5),
    "prize2": (2, 5),
    "prize3": (6, 5),
    "prize4": (4, 4),
    "prize5": (6, 4),
    "prize6": (3, 3),
    "prize7": (4, 2),
}


@dataclass(slots=True)
class Draw:
    date: date
    special: str
    prize1: str
    prize2: list[str] = field(default_factory=list)
    prize3: list[str] = field(default_factory=list)
    prize4: list[str] = field(default_factory=list)
    prize5: list[str] = field(default_factory=list)
    prize6: list[str] = field(default_factory=list)
    prize7: list[str] = field(default_factory=list)

    def validate(self) -> None:
        for prize, (count, width) in PRIZE_SHAPE.items():
            value = getattr(self, prize)
            items = [value] if isinstance(value, str) else value
            if len(items) != count:
                raise ValueError(f"{self.date} {prize}: expected {count} numbers, got {len(items)}")
            for n in items:
                if len(n) != width or not n.isdigit():
                    raise ValueError(f"{self.date} {prize}: bad number {n!r} (need {width} digits)")

    def to_row(self) -> dict[str, str]:
        row: dict[str, str] = {
            "date": self.date.isoformat(),
            "special": self.special,
            "prize1": self.prize1,
        }
        for prize in ("prize2", "prize3", "prize4", "prize5", "prize6", "prize7"):
            for i, n in enumerate(getattr(self, prize), start=1):
                row[f"{prize}_{i}"] = n
        return row


CSV_COLUMNS: list[str] = ["date", "special", "prize1"] + [
    f"{prize}_{i}"
    for prize in ("prize2", "prize3", "prize4", "prize5", "prize6", "prize7")
    for i in range(1, PRIZE_SHAPE[prize][0] + 1)
]
