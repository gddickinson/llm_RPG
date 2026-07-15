"""Event-log display filter tests (George's readability request)."""

import unittest

from engine.event_filter import (categorize, cycle_verbosity,
                                 filtered_recent, should_display,
                                 verbosity)
from engine.game_engine import GameEngine


class TestEventFilter(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_categorization(self):
        self.assertEqual(categorize("[!] You are BURNING!"),
                         "critical")
        self.assertEqual(categorize("[Realm] A caravan is coming."),
                         "news")
        self.assertEqual(categorize("[Law] There's a price on you."),
                         "law")
        self.assertEqual(categorize("You move to wilderness (5, 5)."),
                         "ambient")
        self.assertEqual(categorize("You pick up Bread."), "player")
        self.assertEqual(
            categorize("Wolf attacks Player for 4 damage!"), "combat")

    def test_npc_idle_barks_are_ambient(self):
        # the exact background-life lines George saw leaking through
        self.assertEqual(
            categorize("Grimjaw sleeps peacefully."), "ambient")
        self.assertEqual(
            categorize("Mire Stalker waits in the reeds."), "ambient")
        self.assertEqual(
            categorize("Bram sleeps and recovers 3 HP."), "ambient")
        self.assertEqual(
            categorize("Elda works on the loom."), "ambient")
        self.assertEqual(
            categorize("A guard moves north."), "ambient")
        # a real event with a similar word is NOT swallowed
        self.assertEqual(
            categorize("Bandit attacks Grimjaw for 5 damage!"), "combat")

    def test_normal_hides_npc_idle_barks(self):
        self.engine.player.metadata["log_verbosity"] = "normal"
        for line in ("Grimjaw sleeps peacefully.",
                     "Mire Stalker waits in the reeds.",
                     "A merchant tends the stall."):
            self.assertFalse(
                should_display(self.engine, line),
                f"idle bark should be hidden on normal: {line!r}")
        # verbose players who want the full sim still get them
        self.engine.player.metadata["log_verbosity"] = "verbose"
        self.assertTrue(should_display(
            self.engine, "Grimjaw sleeps peacefully."))

    def test_normal_hides_footsteps_keeps_the_rest(self):
        self.engine.player.metadata["log_verbosity"] = "normal"
        self.assertFalse(should_display(
            self.engine, "You move to wilderness (5, 5)."))
        self.assertTrue(should_display(
            self.engine, "You pick up Bread."))
        self.assertTrue(should_display(
            self.engine, "[!] You are DYING 2/4!"))
        self.assertTrue(should_display(
            self.engine, "[Realm] A shortage grips Oakvale."))

    def test_quiet_drops_law_and_social(self):
        self.engine.player.metadata["log_verbosity"] = "quiet"
        self.assertFalse(should_display(
            self.engine, "[Law] The guard eyes you."))
        self.assertTrue(should_display(
            self.engine, "Wolf attacks Player for 4 damage!"))
        self.assertTrue(should_display(
            self.engine, "[!] Find air!"))

    def test_verbose_shows_everything(self):
        self.engine.player.metadata["log_verbosity"] = "verbose"
        for line in ("You move to wilderness (5, 5).",
                     "[Law] eyes you", "Melody hums a tune."):
            self.assertTrue(should_display(self.engine, line))

    def test_inside_a_building_hides_the_street(self):
        # force "indoors" by entering the nearest interior
        loc = next(iter(self.engine.interiors))
        self.engine.current_interior = self.engine.interiors[loc]
        self.engine.player.metadata["log_verbosity"] = "verbose"
        # even in verbose, ambient overworld noise is out of sight
        self.assertFalse(should_display(
            self.engine, "[Clash] Guard strikes Bandit!"),
            "you can't see the street fight from inside")
        self.assertFalse(should_display(
            self.engine, "A wolf wanders past."))
        # but news still reaches you, and your own acts show
        self.assertTrue(should_display(
            self.engine, "[Realm] Word spreads of a caravan."))
        self.assertTrue(should_display(
            self.engine, "You search the shelves."))
        self.engine.current_interior = None

    def test_cycle_wraps(self):
        self.engine.player.metadata["log_verbosity"] = "normal"
        self.assertEqual(cycle_verbosity(self.engine), "verbose")
        self.assertEqual(cycle_verbosity(self.engine), "quiet")
        self.assertEqual(cycle_verbosity(self.engine), "normal")

    def test_filtered_recent_thins_the_stream(self):
        mm = self.engine.memory_manager
        self.engine.player.metadata["log_verbosity"] = "normal"
        for i in range(20):
            mm.add_event(f"You move to wilderness ({i}, 0).")
        mm.add_event("You pick up a Sword.")
        shown = filtered_recent(self.engine, 10)
        self.assertIn("You pick up a Sword.", shown)
        self.assertFalse(any("move to wilderness" in s
                             for s in shown),
                         "footsteps don't crowd out the real line")

    def test_default_is_normal(self):
        self.engine.player.metadata.pop("log_verbosity", None)
        self.assertEqual(verbosity(self.engine), "normal")


if __name__ == "__main__":
    unittest.main()
