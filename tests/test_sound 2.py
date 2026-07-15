"""Procedural sound tests (P5.5) — dummy audio driver."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from ui.sound import SoundManager


class TestSound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sm = SoundManager()

    def setUp(self):
        if not self.sm.enabled:
            self.skipTest("mixer unavailable in this environment")
        self.played = []
        self._orig_play = self.sm.play
        self.sm.play = lambda name: self.played.append(name)

    def tearDown(self):
        if self.sm.enabled:
            self.sm.play = self._orig_play

    def test_all_sounds_synthesized(self):
        for name in ("hit", "pickup", "coin", "levelup", "spell",
                     "discover", "defeat", "rain", "storm"):
            self.assertIn(name, self.sm.sounds)

    def test_event_keyword_mapping(self):
        cases = {
            "** Level up! Player is now level 3. **": "levelup",
            "You pick up Iron Sword.": "pickup",
            "You buy Tankard of Ale for 3g.": "coin",
            "[Collection] Discovered: Oakvale Tavern": "discover",
            "[Legend] The Dry Summer: ...": "discover",
            "Wolf attacks Player for 4 damage.": "hit",
            "A Wolf strikes you down!": "defeat",
            "You mine and get Copper Ore. (+18 Mining XP)": "pickup",
        }
        for text, expected in cases.items():
            self.played.clear()
            self.sm.on_event(text)
            self.assertEqual(self.played, [expected],
                             f"'{text}' should play {expected}")

    def test_unmatched_events_are_silent(self):
        self.sm.on_event("Goren sleeps peacefully.")
        self.assertEqual(self.played, [])

    def test_ambient_switches_with_weather(self):
        self.sm.update_ambient("rain")
        self.assertEqual(self.sm._ambient_kind, "rain")
        self.sm.update_ambient("storm")
        self.assertEqual(self.sm._ambient_kind, "storm")
        self.sm.update_ambient("clear")
        self.assertIsNone(self.sm._ambient_kind)

    def test_disabled_manager_is_inert(self):
        quiet = SoundManager.__new__(SoundManager)
        quiet.enabled = False
        quiet.sounds = {}
        quiet._ambient_kind = None
        quiet._ambient_channel = None
        quiet.on_event("You pick up thing")   # must not raise
        quiet.update_ambient("rain")
        quiet.play("hit")


if __name__ == "__main__":
    unittest.main()
