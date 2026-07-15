"""The Murkfen swamp region (P4.5 — regional identity)."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class TestMurkfen(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _swamp_tile(self):
        wmap = self.engine.world.map
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.get_terrain_at(x, y) == TerrainType.SWAMP:
                    return (x, y)
        return None

    def test_murkfen_exists_with_swamp_terrain(self):
        names = [loc.name for loc in self.engine.world.locations]
        self.assertIn("The Murkfen", names)
        self.assertIsNotNone(self._swamp_tile(),
                             "the Murkfen should contain swamp tiles")

    def test_swamp_is_passable_but_slow(self):
        wmap = self.engine.world.map
        spot = None
        for y in range(1, wmap.height - 1):
            for x in range(1, wmap.width - 1):
                if wmap.get_terrain_at(x, y) == TerrainType.SWAMP and \
                        wmap.get_terrain_at(x + 1, y) == TerrainType.SWAMP:
                    spot = (x, y)
                    break
            if spot:
                break
        if spot is None:
            self.skipTest("no adjacent swamp tiles")
        self.player.position = spot
        wmap.place_character(self.player, *spot)
        t0 = self.engine.world.time
        self.assertTrue(self.engine.move_player(1, 0))
        self.assertGreaterEqual(self.engine.world.time - t0, 2,
                                "swamp steps cost extra time")

    def test_swamp_monsters_only_in_swamp(self):
        from world.monsters import encounter_table_for
        swamp = dict(encounter_table_for("swamp"))
        grass = dict(encounter_table_for("grass"))
        self.assertIn("bog_lurker", swamp)
        self.assertIn("marsh_wisp", swamp)
        self.assertNotIn("bog_lurker", grass,
                         "swamp natives must not roam the meadows")
        self.assertIn("wolf", grass)
        self.assertNotIn("wolf", swamp)

    def test_encounters_fire_on_swamp_terrain(self):
        spot = self._swamp_tile()
        if spot is None:
            self.skipTest("no swamp")
        self.player.position = spot
        em = self.engine.encounter_manager
        em._cooldown_until = 0
        em.rng.random = lambda: 0.0   # force the roll
        before = len(self.engine.npc_manager.npcs)
        msg = em.maybe_spawn()
        if msg is None:
            self.skipTest("no valid spawn position near swamp edge")
        self.assertGreater(len(self.engine.npc_manager.npcs), before)
        self.assertTrue("Bog Lurker" in msg or "Marsh Wisp" in msg, msg)

    def test_swamp_foraging_yields_bogcap(self):
        spot = self._swamp_tile()
        if spot is None:
            self.skipTest("no swamp")
        self.player.position = spot
        found = set()
        fm = self.engine.forage_manager
        for i in range(30):
            fm.harvested_at = {}
            msg = fm.forage(*spot)
            found.add(msg)
            ids = [getattr(it, "id", "") for it in self.player.inventory]
            if "bogcap" in ids:
                break
        ids = [getattr(it, "id", "") for it in self.player.inventory]
        self.assertIn("bogcap", ids,
                      "30 forages should yield at least one bogcap")

    def test_antidote_recipe_from_bogcaps(self):
        from items.item_registry import create_item
        self.player.gold = 10
        self.player.inventory.append(create_item("bogcap", quantity=2))
        self.engine.craft("antidote")
        ids = [getattr(it, "id", "") for it in self.player.inventory]
        self.assertIn("antidote", ids)

    def test_swamp_renders(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        from ui.renderer import MapRenderer
        spot = self._swamp_tile()
        if spot is None:
            self.skipTest("no swamp")
        pygame.init()
        renderer = MapRenderer(tile_size=16)
        surface = pygame.Surface((320, 240))
        self.player.position = spot
        renderer.render(surface, self.engine,
                        pygame.Rect(0, 0, 320, 240))


if __name__ == "__main__":
    unittest.main()
