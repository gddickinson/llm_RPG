"""Combat juice: trauma-based screen shake (GAP.5). Pure + deterministic,
fed by the event log, applied by offsetting the map render."""

import unittest

from ui.screen_shake import ScreenShake


class TestScreenShake(unittest.TestCase):
    def test_starts_still(self):
        s = ScreenShake()
        self.assertFalse(s.active)
        self.assertEqual(s.offset(), (0, 0))

    def test_trauma_shakes_then_decays_to_still(self):
        s = ScreenShake()
        s.add(0.6)
        self.assertTrue(s.active)
        self.assertNotEqual(s.offset(), (0, 0))
        # decays to rest within ~half a second
        for _ in range(30):
            s.update(1.0 / 30.0)
        self.assertFalse(s.active)
        self.assertEqual(s.offset(), (0, 0))

    def test_trauma_is_capped(self):
        s = ScreenShake()
        for _ in range(10):
            s.add(0.5)
        self.assertLessEqual(s.trauma, 1.0)

    def test_offset_within_max(self):
        s = ScreenShake(max_offset=7)
        s.add(1.0)
        for _ in range(20):
            dx, dy = s.offset()
            self.assertLessEqual(abs(dx), 7)
            self.assertLessEqual(abs(dy), 7)
            s.update(1.0 / 60.0)

    def test_event_keywords_add_trauma(self):
        s = ScreenShake()
        s.on_event("You strike from the shadows — a SNEAK ATTACK on Goblin!")
        self.assertTrue(s.active)
        s2 = ScreenShake()
        s2.on_event("The weather turns cloudy.")   # no combat → no shake
        self.assertFalse(s2.active)

    def test_disabled_does_not_shake(self):
        s = ScreenShake()
        s.enabled = False
        s.add(1.0)
        s.on_event("Goblin is defeated!")
        self.assertFalse(s.active)
        self.assertEqual(s.offset(), (0, 0))


if __name__ == "__main__":
    unittest.main()
