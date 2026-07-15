"""Floods, damming, digging, rebuilding tests (P10.6)."""

import unittest

from engine.game_engine import GameEngine
from engine.giants import run_night_labor
from world.world_map import TerrainType


class _AlwaysRng:
    def random(self):
        return 0.0


class TestEarthworks(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.player = self.engine.player
        self.flood = self.engine.flood_system
        # a quiet staging corner
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

    def _tick_floods(self, n):
        for _ in range(n):
            self.engine.turn_counter += 1
            self.flood.tick()

    # ------------------------------------------------------- floods

    def test_flood_spreads_over_low_ground(self):
        self.flood.start_flood(self.ox, self.oy, duration=100)
        self._tick_floods(12)
        self.assertEqual(self.wmap.terrain[self.oy][self.ox],
                         TerrainType.WATER)
        self.assertEqual(self.wmap.terrain[self.oy][self.ox + 2],
                         TerrainType.WATER,
                         "the frontier must advance")

    def test_rubble_dam_stops_the_water(self):
        # a north-south dam line two tiles east of the source
        for y in range(self.oy - 4, self.oy + 6):
            self.engine.tile_damage.add_rubble(self.ox + 2, y, 1)
        self.flood.start_flood(self.ox, self.oy, duration=100)
        self._tick_floods(20)
        for y in range(self.oy - 3, self.oy + 5):
            self.assertNotEqual(
                self.wmap.terrain[y][self.ox + 3], TerrainType.WATER,
                "piled debris is a dam — water must not cross")

    def test_flood_recedes_and_restores_terrain(self):
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.FARMLAND
        self.flood.start_flood(self.ox, self.oy, duration=10)
        self._tick_floods(4)
        self.assertEqual(self.wmap.terrain[self.oy][self.ox + 1],
                         TerrainType.WATER)
        self._tick_floods(10)
        self.assertEqual(self.wmap.terrain[self.oy][self.ox],
                         TerrainType.GRASS)
        self.assertEqual(self.wmap.terrain[self.oy][self.ox + 1],
                         TerrainType.FARMLAND,
                         "receding water restores what it drowned")
        self.assertEqual(self.flood.floods, [])
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("recede", log)

    def test_water_laps_around_the_occupied(self):
        self._put_player(self.ox + 1, self.oy)
        self.flood.start_flood(self.ox, self.oy, duration=100)
        self._tick_floods(12)
        self.assertNotEqual(
            self.wmap.terrain[self.oy][self.ox + 1],
            TerrainType.WATER,
            "occupied tiles are never flooded")

    def test_floods_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.flood.start_flood(self.ox, self.oy, duration=100)
        self._tick_floods(4)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="flood")
            self.flood.floods = []
            self.assertTrue(sm.load(self.engine, name="flood"))
            self.assertTrue(self.engine.flood_system.floods,
                            "an active flood must persist")
            self.assertTrue(
                self.engine.flood_system.floods[0]["flooded"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------- digging

    def test_pickaxe_digs_a_tunnel_through_rock(self):
        from items.item_registry import create_item
        self.player.inventory.append(create_item("pickaxe"))
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.MOUNTAIN
        self._put_player(self.ox, self.oy)
        xp0 = self.player.metadata.get("skills", {}).get("mining", 0)
        for _ in range(10):
            self.engine.pickup_item()
            if self.wmap.terrain[self.oy][self.ox + 1] != \
                    TerrainType.MOUNTAIN:
                break
        self.assertEqual(self.wmap.terrain[self.oy][self.ox + 1],
                         TerrainType.GRASS,
                         "enough swings cut the mountain through")
        xp1 = self.player.metadata.get("skills", {}).get("mining", 0)
        self.assertGreater(xp1, xp0, "digging trains Mining")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("tunnel", log.lower())

    def test_no_pickaxe_no_tunnel(self):
        self.player.inventory = [i for i in self.player.inventory
                                 if getattr(i, "id", "") != "pickaxe"]
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.MOUNTAIN
        self._put_player(self.ox, self.oy)
        msg = self.engine.pickup_item()
        self.assertIn("nothing here", msg.lower())
        self.assertEqual(self.wmap.terrain[self.oy][self.ox + 1],
                         TerrainType.MOUNTAIN)

    # ------------------------------------------------------ rebuild

    def test_masons_rebuild_the_breached_wall(self):
        loc = next(l for l in self.engine.world.locations
                   if l.name in self.engine.interiors)
        inter = self.engine.interiors[loc.name]
        bx, by = loc.x, loc.y
        # breach it
        while self.wmap.terrain[by][bx] != TerrainType.RUBBLE:
            self.engine.tile_damage.damage_tile(bx, by, 40, "siege")
        # the hole shows inside
        from engine.earthworks import sync_breaches, \
            footprint_to_perimeter
        sync_breaches(self.engine, loc, inter)
        ix, iy = footprint_to_perimeter(loc, inter, bx, by)
        self.assertEqual(inter.terrain[iy][ix], TerrainType.RUBBLE)
        # clear the debris off the footprint
        self.engine.tile_damage.rubble_depth.pop((bx, by), None)
        self.wmap.set_terrain(bx, by, TerrainType.GRASS)
        run_night_labor(self.engine, _AlwaysRng())
        self.assertEqual(self.wmap.terrain[by][bx],
                         TerrainType.BUILDING,
                         "masons must raise the wall again")
        self.assertEqual(inter.terrain[iy][ix], TerrainType.BUILDING,
                         "the interior hole closes with the wall")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-6:])
        self.assertIn("Masons", log)


if __name__ == "__main__":
    unittest.main()
