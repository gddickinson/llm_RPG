"""OAKVALE T5b — the large-town region (world_kind='oakvale')."""

import unittest

from world.world import World
from world.world_map import TerrainType
from world import town_region


class TestRegionUnit(unittest.TestCase):
    def test_region_size_only_for_oakvale(self):
        self.assertEqual(town_region.region_size("oakvale"),
                         town_region.REGION_SIZE)
        self.assertIsNone(town_region.region_size("default"))
        self.assertIsNone(town_region.region_size("castle"))

    def test_build_plants_a_walled_town(self):
        w = World(*town_region.REGION_SIZE)
        out = town_region.build_oakvale_region(w, seed=7)
        self.assertEqual(out["town"], "Oakvale")
        self.assertGreater(out["buildings"], 100)
        self.assertGreaterEqual(out["gates"], 3)
        town = next((l for l in w.locations
                     if l.name == "Oakvale" and l.get_property("town")), None)
        self.assertIsNotNone(town)

    def test_spawn_is_walkable(self):
        w = World(*town_region.REGION_SIZE)
        town_region.build_oakvale_region(w, seed=7)
        sp = town_region.oakvale_spawn(w)
        self.assertIsNotNone(sp)
        x, y = sp
        self.assertIn(w.map.terrain[y][x],
                      (TerrainType.ROAD, TerrainType.GRASS, TerrainType.BRIDGE))


class TestRegionIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False,
                                world_kind="oakvale")
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_map_is_enlarged(self):
        wm = self.engine.world.map
        self.assertEqual((wm.width, wm.height), town_region.REGION_SIZE)

    def test_a_big_town_of_many_kinds(self):
        bld = [l for l in self.engine.world.locations if l.get_property("kind")]
        self.assertGreater(len(bld), 100, "a large town")
        kinds = {l.get_property("kind") for l in bld}
        for grand in ("cathedral", "hall", "guildhall", "tavern", "inn",
                      "library"):
            self.assertIn(grand, kinds, f"the town has a {grand}")
        self.assertTrue({"smithy", "forge", "armoury"} & kinds,
                        "the town has a blacksmith/armourer")

    def test_player_starts_on_walkable_ground(self):
        x, y = self.engine.player.position
        self.assertIn(self.engine.world.map.terrain[y][x],
                      (TerrainType.ROAD, TerrainType.GRASS, TerrainType.BRIDGE))

    def test_buildings_are_enterable(self):
        # every non-marker building has an interior to walk into
        enterable = [l for l in self.engine.world.locations
                     if l.get_property("kind") not in (None, "well", "stall")]
        with_int = [l for l in enterable if l.name in self.engine.interiors]
        self.assertGreater(len(with_int), 100)
        self.assertEqual(len(with_int), len(enterable),
                         "every home/hall/shop is enterable")

    def test_hero_arrives_on_a_teleport_platform(self):
        px, py = self.engine.player.position
        ws = next((l for l in self.engine.world.locations
                   if l.get_property("waystone") == "waystone_oakvale"), None)
        self.assertIsNotNone(ws, "an arrival waystone")
        self.assertEqual((ws.x, ws.y), (px, py), "the hero wakes ON it")
        # and it is a usable platform on the network
        tn = self.engine.teleport_network
        self.assertIsNotNone(tn.platform_at((px, py)))

    def test_town_is_safe_no_wandering_monsters(self):
        em = self.engine.encounter_manager
        px, py = self.engine.player.position
        self.assertTrue(em._in_safe_zone((px, py)), "the square is safe")
        # nowhere inside the town spawns a wandering monster
        spawns = sum(1 for _ in range(200) if em.maybe_spawn())
        self.assertEqual(spawns, 0, "no monsters wander the walled town")

    def test_visible_sewer_grate_into_the_deepdelve(self):
        from world.world_map import TerrainType
        grate = next((l for l in self.engine.world.locations
                      if l.get_property("sewer_grate")), None)
        self.assertIsNotNone(grate, "a visible sewer grate")
        self.assertEqual(grate.get_property("dungeon_key"), "deepdelve")
        self.assertEqual(self.engine.world.map.terrain[grate.y][grate.x],
                         TerrainType.CAVE,
                         "the grate is a real, enterable way down")
        # it descends into the shared Deepdelve
        self.engine.player.position = (grate.x, grate.y)
        msg = self.engine.enter_dungeon()
        self.assertIn("Deepdelve", msg)
        self.engine.exit_dungeon()


if __name__ == "__main__":
    unittest.main()
