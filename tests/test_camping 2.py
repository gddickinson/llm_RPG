"""Camping + the DM's night tests (P12.6)."""

import unittest

from characters.status_effects import has_effect
from engine.camping import SUPPLY_NEED, camp, night_beat
from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.world_map import TerrainType


class _Rng:
    def __init__(self, rand=0.9, roll=1):
        self.rand = rand
        self.roll = roll

    def random(self):
        return self.rand

    def randint(self, a, b):
        return min(b, max(a, self.roll))


class TestCamping(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 10, self.wmap.height - 8
        for y in range(self.oy - 2, self.oy + 3):
            for x in range(self.ox - 2, self.ox + 4):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _provision(self):
        self.player.inventory = [create_item("bread")
                                 for _ in range(3)]   # 3x4 = 12 >= 8

    def test_supplied_camp_is_a_real_night(self):
        self._provision()
        self.player.metadata.update({"fatigue": 80, "sleep_debt": 2})
        self.player.hp = 5
        self.engine.combat_system.rng = _Rng(rand=0.9)  # no ambush
        lines = camp(self.engine)
        self.assertTrue(lines)
        self.assertEqual(self.player.metadata["sleep_debt"], 0,
                         "a supplied camp is a REAL night")
        self.assertEqual(self.player.metadata["fatigue"], 0)
        self.assertGreater(self.player.hp, 5, "half heal by the fire")
        self.assertLess(len(self.player.inventory), 3,
                        "the camp burned provisions")

    def test_unsupplied_camp_only_dozes(self):
        self.player.inventory = []
        self.player.metadata.update({"fatigue": 80, "sleep_debt": 2})
        lines = camp(self.engine)
        self.assertIn("doze", " ".join(lines).lower())
        self.assertEqual(self.player.metadata["sleep_debt"], 2,
                         "the debt only clears with real sleep")
        self.assertLess(self.player.metadata["fatigue"], 80)

    def test_the_wilds_can_interrupt(self):
        self._provision()
        self.player.hp = self.player.max_hp
        self.engine.combat_system.rng = _Rng(rand=0.1)  # ambush!
        n_before = sum(1 for n in
                       self.engine.npc_manager.npcs.values()
                       if n.is_active())
        lines = camp(self.engine)
        self.assertIn("prowled the camp", " ".join(lines))
        n_after = sum(1 for n in
                      self.engine.npc_manager.npcs.values()
                      if n.is_active())
        self.assertGreater(n_after, n_before,
                           "the interruption is a real creature")

    def test_every_night_ends_with_the_dm(self):
        self._provision()
        self.engine.combat_system.rng = _Rng(rand=0.9)
        lines = camp(self.engine)
        self.assertTrue(any(ln.startswith("[DM]") for ln in lines),
                        "the DM's beat slot is guaranteed")

    def test_the_dm_can_author_the_dream(self):
        self.engine.dm_autonomous.night_scene = \
            "A crowned figure beckons from the treeline."
        msg = night_beat(self.engine)
        self.assertIn("crowned figure", msg)
        self.assertTrue(msg.startswith("[DM]"))
        self.assertIsNone(self.engine.dm_autonomous.night_scene,
                          "an authored scene plays once")

    def test_dreams_draw_from_the_lived_world(self):
        from engine.player_deeds import record_deed
        record_deed(self.engine, "slew the Tyrant of the Depths")
        self.engine.combat_system.rng = _Rng(roll=0)  # pick deeds
        msg = night_beat(self.engine)
        self.assertIn("Tyrant", msg)

    def test_private_room_buys_well_rested_xp(self):
        from engine import rest
        from engine.leveling import award_xp
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      or "inn" in l.name.lower())
        self.wmap.remove_character(self.player)
        self.player.position = (tavern.x + tavern.width // 2,
                                tavern.y + tavern.height // 2)
        self.wmap.place_character(self.player, *self.player.position)
        self.player.gold = 100
        rest.sleep(self.engine)
        self.assertTrue(has_effect(self.player, "well_rested"))
        xp0 = self.player.metadata.get("xp", 0)
        award_xp(self.player, 100)
        self.assertEqual(self.player.metadata["xp"] - xp0, 110,
                         "+10% XP while well rested")

    def test_bunk_when_coin_is_short(self):
        from engine import rest
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      or "inn" in l.name.lower())
        self.wmap.remove_character(self.player)
        self.player.position = (tavern.x + tavern.width // 2,
                                tavern.y + tavern.height // 2)
        self.wmap.place_character(self.player, *self.player.position)
        self.player.gold = 10
        rest.sleep(self.engine)
        self.assertEqual(self.player.gold, 5, "the 5g bunk")
        self.assertFalse(has_effect(self.player, "well_rested"))


if __name__ == "__main__":
    unittest.main()
