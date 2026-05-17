"""Tests for the calendar / seasons system."""

import unittest

from world.calendar import (
    Date, Season, date_from_minutes, minutes_from_date,
    MONTH_NAMES, apply_season_tint, SEASON_TINT,
)


class TestCalendar(unittest.TestCase):
    def test_zero_is_year_1_month_1_day_1(self):
        d = date_from_minutes(0)
        self.assertEqual((d.year, d.month, d.day), (1, 1, 1))
        self.assertEqual((d.hour, d.minute), (0, 0))

    def test_day_rollover(self):
        d = date_from_minutes(24 * 60)
        self.assertEqual(d.day, 2)

    def test_month_rollover(self):
        d = date_from_minutes(30 * 24 * 60)
        self.assertEqual(d.month, 2)
        self.assertEqual(d.day, 1)

    def test_year_rollover(self):
        d = date_from_minutes(12 * 30 * 24 * 60)
        self.assertEqual(d.year, 2)
        self.assertEqual(d.month, 1)

    def test_roundtrip(self):
        m = minutes_from_date(year=3, month=7, day=15, hour=14, minute=30)
        d = date_from_minutes(m)
        self.assertEqual((d.year, d.month, d.day, d.hour, d.minute),
                         (3, 7, 15, 14, 30))

    def test_seasons(self):
        # Month 1 -> spring
        self.assertEqual(date_from_minutes(0).season, Season.SPRING)
        # Month 7 (start) -> autumn
        d = date_from_minutes(minutes_from_date(1, 7, 1))
        self.assertEqual(d.season, Season.AUTUMN)
        # Month 12 -> winter
        d = date_from_minutes(minutes_from_date(1, 12, 1))
        self.assertEqual(d.season, Season.WINTER)

    def test_month_names(self):
        d = date_from_minutes(0)
        self.assertEqual(d.month_name, MONTH_NAMES[0])

    def test_time_of_day(self):
        d = date_from_minutes(minutes_from_date(1, 1, 1, hour=9))
        self.assertEqual(d.time_of_day(), "morning")
        d = date_from_minutes(minutes_from_date(1, 1, 1, hour=14))
        self.assertEqual(d.time_of_day(), "afternoon")
        d = date_from_minutes(minutes_from_date(1, 1, 1, hour=19))
        self.assertEqual(d.time_of_day(), "evening")
        d = date_from_minutes(minutes_from_date(1, 1, 1, hour=23))
        self.assertEqual(d.time_of_day(), "night")

    def test_season_tint_clamps(self):
        rgb = apply_season_tint((255, 255, 255), Season.WINTER)
        for v in rgb:
            self.assertTrue(0 <= v <= 255)


if __name__ == "__main__":
    unittest.main()
