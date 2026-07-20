"""George: a player shouldn't TAB out of a building/dungeon (or change level)
from ANYWHERE — only at a door/stairs; and shouldn't fast-travel from anywhere
— only from a waystone (teleport station)."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from engine.game_engine import GameEngine


class TestExitGating(unittest.TestCase):
    def setUp(self):
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        from ui.gui import GameGUI
        self.gui = GameGUI(self.e, width=480, height=320)

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def _enter_a_building(self):
        loc = next((l for l in self.e.world.locations
                    if l.name in self.e.interiors), None)
        if loc is None:
            self.skipTest("no enterable building")
        self.e.player.position = loc.center()
        self.e.enter_building()
        return self.e.current_interior

    def test_tab_exits_only_at_the_door(self):
        inter = self._enter_a_building()
        dx, dy = inter.door
        # off the door: TAB refuses
        self.e.player.position = (dx, max(1, dy - 2))
        self.gui.input_handler._handle_interact()
        self.assertIsNotNone(self.e.current_interior,
                             "TAB off the door must not exit")
        # at the door: TAB exits
        self.e.player.position = tuple(inter.door)
        self.gui.input_handler._handle_interact()
        self.assertIsNone(self.e.current_interior,
                          "TAB at the door should exit")

    def test_try_exit_zone_helper(self):
        from ui.input_actions import try_exit_zone
        inter = self._enter_a_building()
        self.e.player.position = (inter.door[0], max(1, inter.door[1] - 2))
        self.assertTrue(try_exit_zone(self.gui.input_handler))  # handled (refused)
        self.assertIsNotNone(self.e.current_interior)


class TestTravelGating(unittest.TestCase):
    def setUp(self):
        # waystones seed with the adventurers; enable them for this test
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.ts = self.e.travel_system

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_fast_travel_requires_a_waystone(self):
        p = self.e.player
        dests = self.ts.destinations()
        idx = next((i for i, d in enumerate(dests) if d["unlocked"]), 0)
        # away from a waystone: refused
        self.assertFalse(self.ts.at_station())
        msg = self.ts.teleport(idx)
        self.assertIn("waystone", msg.lower())
        # ON a waystone: allowed (or a normal travel/cooldown/toll message)
        tn = self.e.teleport_network
        if not tn.platforms:
            self.skipTest("no waystones seeded")
        p.position = tuple(tn.platforms[0]["pos"])
        self.assertTrue(self.ts.at_station())
        msg2 = self.ts.teleport(idx)
        self.assertNotIn("only travel from a waystone", msg2.lower())


if __name__ == "__main__":
    unittest.main()
