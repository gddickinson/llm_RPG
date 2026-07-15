"""Surface tests (P10.3) — fire, oil, water, and their chemistry."""

import random
import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from world.monsters import build_monster


class TestSurfaces(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.lay = self.engine.surfaces_layer
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 14, self.wmap.height - 10
        for y in range(self.oy - 2, self.oy + 6):
            for x in range(self.ox - 2, self.ox + 10):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        p = self.engine.player
        self.wmap.remove_character(p)
        p.position = (self.ox - 2, self.oy - 2)
        self.wmap.place_character(p, *p.position)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_standing_in_fire_burns(self):
        wolf = build_monster("wolf", (self.ox, self.oy))
        wolf.hp = wolf.max_hp = 30
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        self.lay.ignite(self.ox, self.oy)
        self.lay.tick()
        self.assertLess(wolf.hp, 30)

    def test_fire_can_kill_and_it_counts(self):
        wolf = build_monster("wolf", (self.ox, self.oy))
        wolf.hp = wolf.max_hp = 4
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        self.lay.ignite(self.ox, self.oy)
        self.lay.tick()
        self.assertFalse(wolf.is_active(),
                         "flame deaths are real deaths")

    def test_fire_never_kills_the_player_outright(self):
        p = self.engine.player
        self.wmap.remove_character(p)
        p.position = (self.ox, self.oy)
        self.wmap.place_character(p, *p.position)
        p.hp = 2
        self.lay.ignite(self.ox, self.oy)
        self.lay.tick()
        self.assertGreaterEqual(p.hp, 1,
                                "fire maims; the story kills")

    def test_fire_spreads_through_the_forest(self):
        for x in range(self.ox, self.ox + 5):
            self.wmap.terrain[self.oy][x] = TerrainType.FOREST
        self.lay.rng = random.Random(1)
        self.lay.ignite(self.ox, self.oy, duration=10)
        for _ in range(8):
            self.lay.tick()
        burning = [p for p, s in self.lay.surfaces.items()
                   if s["kind"] == "fire"]
        scorched = [1 for x in range(self.ox, self.ox + 5)
                    if self.wmap.terrain[self.oy][x] ==
                    TerrainType.SCORCHED]
        self.assertTrue(len(burning) + len(scorched) > 1,
                        "fire must travel")

    def test_burnt_grove_is_scorched_earth(self):
        self.wmap.terrain[self.oy][self.ox] = TerrainType.FOREST
        self.lay.ignite(self.ox, self.oy, duration=8)
        for _ in range(8):
            self.lay.tick()
        self.assertEqual(self.wmap.terrain[self.oy][self.ox],
                         TerrainType.SCORCHED)

    def test_oil_pool_chain_ignites(self):
        self.lay.pour(self.ox, self.oy, "oil", radius=2)
        pool = sum(1 for s in self.lay.surfaces.values()
                   if s["kind"] == "oil")
        self.assertGreater(pool, 5)
        lit = self.lay.ignite(self.ox, self.oy)
        self.assertEqual(lit, pool,
                         "the whole pool goes up at once")

    def test_water_douses(self):
        self.lay.ignite(self.ox, self.oy, duration=20)
        self.assertTrue(self.lay.douse(self.ox, self.oy))
        self.assertEqual(self.lay.kind_at(self.ox, self.oy), "water")
        # and water refuses ignition
        self.assertEqual(self.lay.ignite(self.ox, self.oy), 0)

    def test_fires_gutter_out(self):
        self.lay.ignite(self.ox, self.oy, duration=3)
        for _ in range(4):
            self.lay.tick()
        self.assertIsNone(self.lay.kind_at(self.ox, self.oy))

    def test_fireball_leaves_flames(self):
        p = self.engine.player
        wolf = build_monster("wolf", (self.ox + 3, self.oy))
        wolf.hp = wolf.max_hp = 99
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        self.wmap.remove_character(p)
        p.position = (self.ox, self.oy)
        self.wmap.place_character(p, *p.position)
        p.metadata["spells_known"] = ["fireball"]
        p.metadata["mana"] = 40
        p.metadata["max_mana"] = 40
        self.engine.cast_spell("fireball", wolf.name)
        self.assertEqual(self.lay.kind_at(self.ox + 3, self.oy),
                         "fire", "the impact keeps burning")

    def test_surfaces_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.lay.pour(self.ox, self.oy, "oil", radius=1)
        count = len(self.lay.surfaces)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="fire")
            self.lay.surfaces = {}
            self.assertTrue(sm.load(self.engine, name="fire"))
            self.assertEqual(
                len(self.engine.surfaces_layer.surfaces), count)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
