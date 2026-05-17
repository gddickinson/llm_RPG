"""Tests for NPC needs and schedules."""

import unittest

from characters.needs import (
    tick_needs, feed, rest, get_hunger, get_fatigue,
    need_descriptor,
    HUNGER_HUNGRY, FATIGUE_TIRED,
)
from characters.schedules import (
    schedule_for, current_entry, activity_to_action, SCHEDULES,
)


class FakeNPC:
    def __init__(self):
        self.metadata = {}


class TestNeeds(unittest.TestCase):
    def test_ticking_increases_hunger(self):
        n = FakeNPC()
        h0 = get_hunger(n)
        tick_needs(n, elapsed_minutes=60)
        self.assertGreater(get_hunger(n), h0)

    def test_feeding_reduces_hunger(self):
        n = FakeNPC()
        for _ in range(20):  # boost hunger high
            tick_needs(n, elapsed_minutes=60)
        before = get_hunger(n)
        feed(n, amount=50)
        self.assertLess(get_hunger(n), before)

    def test_rest_reduces_fatigue(self):
        n = FakeNPC()
        for _ in range(40):
            tick_needs(n, elapsed_minutes=60)
        before = get_fatigue(n)
        rest(n, amount=60)
        self.assertLess(get_fatigue(n), before)

    def test_descriptor(self):
        n = FakeNPC()
        # All zero -> comfortable
        self.assertEqual(need_descriptor(n), "comfortable")
        # Force hunger high
        n.metadata["hunger"] = HUNGER_HUNGRY + 1
        self.assertIn("hungry", need_descriptor(n))


class TestSchedules(unittest.TestCase):
    def test_known_classes(self):
        for klass in ("merchant", "guard", "villager", "bard", "cleric"):
            self.assertTrue(schedule_for(klass))

    def test_current_entry_morning(self):
        e = current_entry("merchant", 9)
        self.assertIsNotNone(e)
        # Should be the "work" entry (starts at 8)
        self.assertEqual(e[1], "work")

    def test_current_entry_overnight(self):
        # At 2am, should wrap to the latest entry from previous day (sleep)
        e = current_entry("merchant", 2)
        self.assertIsNotNone(e)
        self.assertEqual(e[1], "sleep")

    def test_unknown_class(self):
        self.assertEqual(schedule_for("nonsense"), [])
        self.assertIsNone(current_entry("nonsense", 12))

    def test_activity_translation(self):
        act, tgt = activity_to_action("sleep", "home")
        self.assertEqual(act, "sleep")
        act, _ = activity_to_action("work", "shop")
        self.assertEqual(act, "move")


if __name__ == "__main__":
    unittest.main()
