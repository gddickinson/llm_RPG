"""The apex tier — dragons & the reachable bosses (P19.1).

The game had no dragons and its boss-tier monsters (warlord, wisp queen,
hill tyrant) were `encounter_weight: 0` dead content reachable only in
tests. This round adds a dragon family and an apex pool so a deep
dungeon's den-lord is drawn from the boss tier — the built content
finally sees play, and a wyrm waits in the deep dark."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import random
import unittest

from engine.game_engine import GameEngine
from engine import bosses
from world.monsters import apex_pool, build_monster, MONSTER_TEMPLATES
from world.dungeon import generate_dungeon, populate_dungeon
from world.world_map import TerrainType
from characters.status_effects import effect_value


class TestApexData(unittest.TestCase):
    def test_the_dragon_family_exists(self):
        for tid in ("dragon_whelp", "young_dragon", "elder_dragon"):
            self.assertIn(tid, MONSTER_TEMPLATES, f"{tid} missing")
            self.assertEqual(MONSTER_TEMPLATES[tid]["race"], "dragonborn")

    def test_dragons_are_bosses_that_breathe(self):
        for tid in ("young_dragon", "elder_dragon"):
            boss = MONSTER_TEMPLATES[tid]["behavior"]["boss"]
            self.assertEqual(boss["telegraph"]["kind"], "breath")
            self.assertTrue(boss["phases"], "a dragon has phases")

    def test_dragons_do_not_wander_the_wild(self):
        # apex creatures are lair/dungeon content, never random spawns
        for tid in ("young_dragon", "elder_dragon", "dragon_whelp"):
            self.assertEqual(
                MONSTER_TEMPLATES[tid].get("encounter_weight", 0), 0)


class TestApexPool(unittest.TestCase):
    def test_shallow_has_no_apex(self):
        self.assertEqual(apex_pool(1), [])

    def test_the_built_bosses_are_reachable(self):
        # the formerly dead content now opts in via boss_depth
        pool = apex_pool(3)
        for tid in ("wisp_queen", "giant_warlord", "tyrant_depths"):
            self.assertIn(tid, pool, f"{tid} should be reachable by depth 3")

    def test_a_dragon_waits_in_the_deep(self):
        self.assertNotIn("young_dragon", apex_pool(2))
        self.assertIn("young_dragon", apex_pool(3))
        self.assertNotIn("elder_dragon", apex_pool(4))
        self.assertIn("elder_dragon", apex_pool(5))

    def test_pool_only_grows_with_depth(self):
        self.assertTrue(set(apex_pool(3)).issubset(set(apex_pool(5))))


class TestDragonMechanics(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        # a clear overworld patch with the player in the middle
        for yy in range(8, 16):
            for xx in range(8, 16):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        self.engine.world.map.remove_character(self.p)
        self.p.position = (12, 12)
        self.engine.world.map.place_character(self.p, 12, 12)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _dragon(self, at=(14, 12)):
        d = build_monster("young_dragon", at)
        self.engine.npc_manager.add_npc(d)
        self.engine.world.map.place_character(d, *at)
        return d

    def test_breath_sets_the_ground_ablaze(self):
        d = self._dragon()
        bosses.boss_tick(self.engine, d)      # aim at the player
        self.assertIsNotNone(d.metadata.get("boss_mark"))
        bosses.boss_tick(self.engine, d)      # detonate the mark
        fires = [pos for pos, s in self.engine.surfaces_layer.surfaces.items()
                 if s.get("kind") == "fire"]
        self.assertTrue(fires, "dragonfire must leave the ground burning")

    def test_the_roar_frightens(self):
        d = self._dragon()
        self.assertEqual(effect_value(self.p, "frightened"), 0)
        d.hp = int(d.max_hp * 0.4)            # cross the 0.5 terror threshold
        bosses.boss_on_damaged(self.engine, d)
        self.assertGreater(effect_value(self.p, "frightened"), 0,
                           "a dragon's roar should Frighten the player")

    def test_a_dragon_is_a_real_threat(self):
        # it does not fold like a wild monster: flee_below 0 = never routs
        d = self._dragon()
        self.assertEqual(
            d.metadata["behavior"].get("flee_below"), 0.0)
        self.assertGreaterEqual(d.max_hp, 100)


class TestDungeonApex(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_deep_boss_floor_crowns_an_apex(self):
        rng = random.Random(4)
        d = generate_dungeon(name="Deeptest Hollow", seed=4)
        d.depth = 4                            # a deep floor…
        d.level_below = None                   # …that is the bottom
        populate_dungeon(d, self.engine, rng)
        apex_names = {MONSTER_TEMPLATES[t]["name"] for t in apex_pool(4)}
        zone_mobs = [n for n in self.engine.npc_manager.npcs.values()
                     if (n.metadata or {}).get("zone") == d.name]
        self.assertTrue(zone_mobs, "the dungeon should be populated")
        self.assertTrue(any(n.name in apex_names for n in zone_mobs),
                        "the deepest floor's den-lord is a boss-tier apex")


if __name__ == "__main__":
    unittest.main()
