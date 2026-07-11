"""Flight & speed magic tests (P11.4)."""

import unittest

from characters.status_effects import apply_effect, remove_effect
from engine.game_engine import GameEngine
from engine.hazards import water_hazard_tick
from world.monsters import build_monster
from world.world_map import TerrainType


class TestFlight(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.player = self.engine.player
        self.ox, self.oy = self.wmap.width - 12, self.wmap.height - 10
        for y in range(self.oy - 4, self.oy + 6):
            for x in range(self.ox - 4, self.ox + 8):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put_player(self, x, y):
        self.wmap.remove_character(self.player)
        self.player.position = (x, y)
        self.wmap.place_character(self.player, x, y)

    def test_flying_player_crosses_water_and_rock(self):
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.WATER
        self.wmap.terrain[self.oy][self.ox + 2] = TerrainType.MOUNTAIN
        self._put_player(self.ox, self.oy)
        apply_effect(self.player, "flying", 20)
        self.assertTrue(self.engine.player_actions.move(1, 0))
        hp0 = self.player.hp
        water_hazard_tick(self.engine)
        self.assertEqual(self.player.hp, hp0,
                         "no struggle above the water")
        self.assertTrue(self.engine.player_actions.move(1, 0))
        self.assertEqual(self.player.position,
                         (self.ox + 2, self.oy))

    def test_landing_restores_the_ground_rules(self):
        # a 3x3 pool; the player hangs above its deep center
        for dy in (-1, 0, 1):
            for dx in (0, 1, 2):
                self.wmap.terrain[self.oy + dy][self.ox + dx] = \
                    TerrainType.WATER
        self._put_player(self.ox + 1, self.oy)
        apply_effect(self.player, "flying", 20)
        self.engine.traversal.rng = type(
            "R", (), {"randint": lambda s, a, b: 1})()
        hp0 = self.player.hp
        water_hazard_tick(self.engine)
        self.assertEqual(self.player.hp, hp0, "airborne and dry")
        remove_effect(self.player, "flying")
        water_hazard_tick(self.engine)
        self.assertLess(self.player.hp, hp0,
                        "grounded, the water is real again")

    def test_flying_ignores_deep_rubble(self):
        self.engine.tile_damage.add_rubble(self.ox + 1, self.oy, 3)
        self._put_player(self.ox, self.oy)
        self.assertFalse(self.engine.player_actions.move(1, 0),
                         "deep rubble blocks the walker")
        apply_effect(self.player, "flying", 20)
        self.assertTrue(self.engine.player_actions.move(1, 0),
                        "the flier passes over the pile")

    def test_wisps_fly_wolves_do_not(self):
        self.wmap.terrain[self.oy][self.ox] = TerrainType.WATER
        wisp = build_monster("marsh_wisp", (self.ox + 1, self.oy))
        self.wmap.place_character(wisp, *wisp.position)
        self.assertTrue(self.wmap.move_character(wisp, self.ox,
                                                 self.oy))
        wolf = build_monster("wolf", (self.ox + 1, self.oy))
        self.wmap.place_character(wolf, *wolf.position)
        self.wmap.move_character(wisp, self.ox + 2, self.oy - 2)
        self.assertFalse(self.wmap.move_character(wolf, self.ox,
                                                  self.oy))

    def test_haste_gives_a_free_step(self):
        self._put_player(self.ox, self.oy)
        apply_effect(self.player, "hasted", 20)
        t0 = self.engine.turn_counter
        self.engine.player_actions.move(1, 0)
        self.engine.player_actions.move(1, 0)
        self.assertEqual(self.engine.turn_counter - t0, 1,
                         "two steps, one turn — the world lags")

    def test_slow_doubles_the_cost(self):
        self._put_player(self.ox, self.oy)
        apply_effect(self.player, "slowed", 20)
        t0 = self.engine.turn_counter
        self.engine.player_actions.move(1, 0)
        self.assertEqual(self.engine.turn_counter - t0, 2,
                         "one step, two turns — time thickens")

    def test_slowed_npcs_act_every_other_turn(self):
        wolf = build_monster("wolf", (self.ox + 3, self.oy + 3))
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        apply_effect(wolf, "slowed", 20)
        router = self.engine.action_router
        acted = [router.process(wolf, {"action": "wait"})
                 for _ in range(4)]
        self.assertEqual(acted[0::2], [False, False],
                         "every other action is lost to the spell")

    def test_speed_spells_are_data_and_self_cast(self):
        from engine.spells import SPELL_REGISTRY
        for sid in ("flight", "haste", "slow"):
            self.assertIn(sid, SPELL_REGISTRY)
        self.player.metadata["spells_known"] = ["flight", "haste"]
        self.player.metadata["mana"] = 30
        self.player.metadata["max_mana"] = 30
        self.engine.cast_spell("flight")
        self.engine.cast_spell("haste")
        from characters.status_effects import has_effect
        self.assertTrue(has_effect(self.player, "flying"))
        self.assertTrue(has_effect(self.player, "hasted"))


if __name__ == "__main__":
    unittest.main()
