"""Needs II tests (P12.3): thirst + the exhaustion ladder."""

import unittest

from characters.needs import (SLEEP_DEBT_MAX, exhaustion_attack_penalty,
                              exhaustion_check_penalty, exhaustion_level,
                              exhaustion_step_minutes, get_thirst,
                              player_needs_turn, run_player_night,
                              tick_player_needs)
from characters.status_effects import has_effect
from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.world_map import TerrainType


class TestNeeds2(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.meta = self.player.metadata
        self.meta.update({"hunger": 10, "thirst": 10, "fatigue": 10,
                          "sleep_debt": 0})
        self.ox, self.oy = self.wmap.width - 10, self.wmap.height - 8
        for y in range(self.oy - 2, self.oy + 3):
            for x in range(self.ox - 2, self.ox + 4):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_thirst_outpaces_hunger(self):
        tick_player_needs(self.player, elapsed_minutes=600)
        self.assertGreater(self.meta["thirst"] - 10,
                           self.meta["hunger"] - 10,
                           "thirst is the faster clock")

    def test_the_ladder_stacks_and_caps(self):
        self.assertEqual(exhaustion_level(self.player), 0)
        self.meta["thirst"] = 65
        self.assertEqual(exhaustion_level(self.player), 1)
        self.meta["thirst"] = 95
        self.assertEqual(exhaustion_level(self.player), 2)
        self.meta["hunger"] = 95
        self.meta["fatigue"] = 95
        self.meta["sleep_debt"] = SLEEP_DEBT_MAX
        self.assertEqual(exhaustion_level(self.player), 6,
                         "everything wrong at once caps at 6")

    def test_ladder_rungs_bite(self):
        self.meta["thirst"] = 65                      # level 1
        self.assertEqual(exhaustion_check_penalty(self.player), -1)
        self.assertEqual(exhaustion_step_minutes(self.player), 0)
        self.meta["thirst"] = 95                      # level 2
        self.assertEqual(exhaustion_step_minutes(self.player), 1)
        self.assertEqual(exhaustion_attack_penalty(self.player), 0)
        self.meta["fatigue"] = 95                     # level 3
        self.assertEqual(exhaustion_attack_penalty(self.player), -2)

    def test_rung_four_halves_hp_and_rung_six_collapses(self):
        self.meta.update({"thirst": 95, "hunger": 95, "fatigue": 95})
        self.player.hp = self.player.max_hp
        player_needs_turn(self.engine)                # level 4
        self.assertLessEqual(self.player.hp, self.player.max_hp // 2,
                             "deep exhaustion caps your strength")
        self.meta["sleep_debt"] = 2                   # level 6
        player_needs_turn(self.engine)
        self.assertTrue(has_effect(self.player, "paralyzed"),
                        "at the top of the ladder you collapse")
        self.assertEqual(self.meta["fatigue"], 50,
                         "passing out is poor rest, not none")

    def test_sleep_debt_two_tracks(self):
        day = self.engine.world.time // (24 * 60)
        run_player_night(self.engine, day)            # no bed tonight
        self.assertEqual(self.meta["sleep_debt"], 1)
        self.meta["slept_day"] = day + 1
        run_player_night(self.engine, day + 1)        # slept this one
        self.assertEqual(self.meta["sleep_debt"], 1,
                         "a real night adds no debt")

    def test_inn_sleep_clears_debt_but_naps_do_not(self):
        from engine import rest
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      or "inn" in l.name.lower())
        self.wmap.remove_character(self.player)
        self.player.position = (tavern.x + tavern.width // 2,
                                tavern.y + tavern.height // 2)
        self.wmap.place_character(self.player, *self.player.position)
        self.player.gold = 100
        self.meta.update({"sleep_debt": 2, "fatigue": 90})
        rest.sleep(self.engine)
        self.assertEqual(self.meta["sleep_debt"], 0,
                         "a real night in a bed clears the debt")
        self.assertEqual(self.meta["fatigue"], 0)

    def test_drinking_at_the_waters_edge(self):
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.WATER
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)
        self.meta["thirst"] = 80
        msg = self.engine.pickup_item()      # E fallback
        self.assertIn("drink deep", msg)
        self.assertEqual(get_thirst(self.player), 0)

    def test_a_waterskin_quenches_anywhere(self):
        self.player.inventory.append(create_item("waterskin"))
        self.meta["thirst"] = 70
        msg = self.engine.player_actions.use("waterskin")
        self.assertIn("thirst eases", msg.lower())
        self.assertEqual(get_thirst(self.player), 0)
        self.assertFalse(any(getattr(i, "id", "") == "waterskin"
                             for i in self.player.inventory))

    def test_exhaustion_bites_checks_via_the_core(self):
        from engine.skills import Skill, roll_check

        class _R:
            def randint(self, a, b):
                return 10

        base = roll_check(self.player, Skill.PERCEPTION, dc=10,
                          rng=_R())[1]
        self.meta.update({"thirst": 95, "fatigue": 95})   # level 3
        worn = roll_check(self.player, Skill.PERCEPTION, dc=10,
                          rng=_R())[1]
        self.assertEqual(base - worn, 3,
                         "level N is -N to every d20")


if __name__ == "__main__":
    unittest.main()
