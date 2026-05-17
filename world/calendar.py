"""Calendar / time / seasons.

The world's clock is stored as `world.time` (minutes since campaign start).
This module turns that into a structured Date and exposes seasons.

Calendar (intentionally simple):
- 12 months, 30 days each (360-day year)
- 4 seasons of 3 months each
- Day starts at hour 0 (midnight)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

DAY_MINUTES = 24 * 60
MONTH_DAYS = 30
MONTHS_PER_YEAR = 12


class Season(Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


MONTH_NAMES = [
    "Frostfall", "Awakening", "Bloomtide",       # spring
    "Sunreach", "Highsun", "Goldgrass",          # summer
    "Harvest", "Emberfall", "Mistwane",          # autumn
    "Longnight", "Deepfrost", "Iceveil",         # winter
]


SEASON_FOR_MONTH = (
    [Season.SPRING] * 3 +
    [Season.SUMMER] * 3 +
    [Season.AUTUMN] * 3 +
    [Season.WINTER] * 3
)


# Per-season tint applied as a multiplier over base tile colors (R, G, B)
SEASON_TINT = {
    Season.SPRING: (1.00, 1.10, 0.95),
    Season.SUMMER: (1.05, 1.00, 0.90),
    Season.AUTUMN: (1.10, 0.80, 0.70),
    Season.WINTER: (0.85, 0.95, 1.20),
}


@dataclass(frozen=True)
class Date:
    year: int          # 1+
    month: int         # 1..12
    day: int           # 1..30
    hour: int          # 0..23
    minute: int        # 0..59

    @property
    def season(self) -> Season:
        return SEASON_FOR_MONTH[self.month - 1]

    @property
    def month_name(self) -> str:
        return MONTH_NAMES[self.month - 1]

    def format(self) -> str:
        return (
            f"{self.month_name} {self.day}, Year {self.year} "
            f"({self.hour:02d}:{self.minute:02d}) — {self.season.value}"
        )

    def time_of_day(self) -> str:
        h = self.hour
        if 5 <= h < 12:
            return "morning"
        if 12 <= h < 17:
            return "afternoon"
        if 17 <= h < 21:
            return "evening"
        return "night"


def date_from_minutes(total_minutes: int) -> Date:
    """Convert raw minute count to a structured Date."""
    minute = total_minutes % 60
    total_hours = total_minutes // 60
    hour = total_hours % 24
    total_days = total_hours // 24
    day_idx = total_days % MONTH_DAYS
    total_months = total_days // MONTH_DAYS
    month_idx = total_months % MONTHS_PER_YEAR
    year = total_months // MONTHS_PER_YEAR + 1
    return Date(
        year=year,
        month=month_idx + 1,
        day=day_idx + 1,
        hour=hour,
        minute=minute,
    )


def minutes_from_date(year: int, month: int, day: int,
                      hour: int = 0, minute: int = 0) -> int:
    return (
        (year - 1) * MONTHS_PER_YEAR * MONTH_DAYS * DAY_MINUTES
        + (month - 1) * MONTH_DAYS * DAY_MINUTES
        + (day - 1) * DAY_MINUTES
        + hour * 60
        + minute
    )


def apply_season_tint(rgb: Tuple[int, int, int], season: Season
                      ) -> Tuple[int, int, int]:
    """Multiply an RGB tile color by the seasonal tint, clamped to [0,255]."""
    tr, tg, tb = SEASON_TINT[season]
    return (
        max(0, min(255, int(rgb[0] * tr))),
        max(0, min(255, int(rgb[1] * tg))),
        max(0, min(255, int(rgb[2] * tb))),
    )
