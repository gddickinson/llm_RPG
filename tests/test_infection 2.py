"""Infection race tests (P12.12): three numbers, first to 100."""

import unittest

from engine.game_engine import GameEngine
from engine.infection import (CRISIS_RESET, infected, infection_night,
                              maybe_infect, treat)
from engine.skills import Degree
from items.item_registry import create_item


class _Rng:
    def __init__(self, roll=10, rand=0.5):
        self.roll = roll
        self.rand = rand

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def random(self):
        return self.rand


class TestInfection(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.meta = self.player.metadata

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _infect(self, progress=20.0, immunity=0.0):
        self.meta["infection"] = {"progress": progress,
                                  "immunity": immunity,
                                  "cause": "a test wound"}

    def test_dirty_wounds_can_turn(self):
        self.engine.combat_system.rng = _Rng(rand=0.1)
        self.assertTrue(maybe_infect(self.engine, 0.30, "the fall"))
        self.assertTrue(infected(self.player))
        self.engine.combat_system.rng = _Rng(rand=0.9)
        self.meta["infection"] = None
        self.assertFalse(maybe_infect(self.engine, 0.30))

    def test_one_infection_at_a_time(self):
        self._infect()
        self.engine.combat_system.rng = _Rng(rand=0.0)
        self.assertFalse(maybe_infect(self.engine, 1.0))

    def test_bed_rest_wins_the_race(self):
        self._infect(progress=20, immunity=60)
        self.meta["slept_quality"] = "bed"
        infection_night(self.engine)
        # 60 + 21*1.5 = 91.5 — one more good night wins
        self.meta["slept_quality"] = "bed"
        infection_night(self.engine)
        self.assertFalse(infected(self.player),
                         "immunity hit 100 first")

    def test_sleepless_nights_lose_ground(self):
        self._infect(progress=20, immunity=0)
        infection_night(self.engine)      # no slept_quality: x0.6
        inf = self.meta["infection"]
        self.assertEqual(inf["progress"], 48)
        self.assertAlmostEqual(inf["immunity"], 12.6, places=1)

    def test_the_crisis_drops_you(self):
        self._infect(progress=90, immunity=10)
        infection_night(self.engine)      # progress crosses 100
        from engine.dying import is_dying
        self.assertTrue(is_dying(self.player),
                        "the fever crisis is a P12.4 dying state")
        self.assertEqual(self.meta["infection"]["progress"],
                         CRISIS_RESET, "the fever breaks back")

    def test_treatment_subtracts(self):
        self._infect(progress=50)
        note = treat(self.engine, Degree.SUCCESS)
        self.assertIn("-20", note)
        self.assertEqual(self.meta["infection"]["progress"], 30)
        note = treat(self.engine, Degree.CRIT_SUCCESS)
        self.assertFalse(infected(self.player),
                         "a crit treatment finished it")
        self.assertIn("beaten", note)

    def test_battle_medicine_treats_the_wound(self):
        from engine.skill_actions import battle_medicine
        self._infect(progress=60)
        self.player.inventory = [create_item("bandage")]
        self.player.hp = 5
        self.engine.combat_system.rng = _Rng(roll=15)
        msg = battle_medicine(self.engine)
        self.assertIn("infected wound", msg)
        self.assertLess(self.meta["infection"]["progress"], 60)

    def test_a_priest_at_your_shoulder_helps(self):
        cleric = next(n for n in self.engine.npc_manager.npcs.values()
                      if n.is_active() and
                      getattr(n.character_class, "value", "")
                      == "cleric")
        px, py = self.player.position
        self.engine.world.map.remove_character(cleric)
        cleric.position = (px + 1, py)
        self.engine.world.map.place_character(cleric, px + 1, py)
        self._infect(progress=50)
        note = treat(self.engine, Degree.SUCCESS)
        self.assertIn("steady hands", note)
        self.assertEqual(self.meta["infection"]["progress"], 20,
                         "-20 for the dressing, -10 for the priest")

    def test_the_hint_shows_the_race(self):
        from engine.infection import hint
        self.assertEqual(hint(self.engine), "")
        self._infect(progress=48, immunity=12)
        line = hint(self.engine)
        self.assertIn("48", line)
        self.assertIn("12", line)


if __name__ == "__main__":
    unittest.main()
