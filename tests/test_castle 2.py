"""Bloodstone Castle (Phase 18) — the multi-level castle structure builds,
links, loots and populates as authored."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from world.location import Location
from world.structures import STRUCTURES, StructureBuilder


class TestCastleData(unittest.TestCase):
    def test_the_castle_is_a_seven_floor_fortress(self):
        castle = STRUCTURES.get("bloodstone_castle")
        self.assertIsNotNone(castle, "the castle ships in structures.json")
        self.assertEqual(castle["attach_to"], "Bloodstone Castle")
        self.assertEqual(len(castle["levels"]), 7)
        names = [lv["name"] for lv in castle["levels"]]
        self.assertTrue(any("Battlements" in n for n in names))
        self.assertTrue(any("Great Hall" in n for n in names))
        self.assertTrue(any("Crypt" in n for n in names))
        # floors run +2 (battlements) down to -4 (crypt), one ground floor
        floors = sorted(lv["floor"] for lv in castle["levels"])
        self.assertEqual(floors, [-4, -3, -2, -1, 0, 1, 2])

    def test_the_grids_are_rectangular_and_walled(self):
        for lv in STRUCTURES["bloodstone_castle"]["levels"]:
            grid = lv["grid"]
            w = len(grid[0])
            for row in grid:
                self.assertEqual(len(row), w, f"{lv['name']} ragged grid")
            # the outer ring is wall on the top and bottom rows
            self.assertTrue(set(grid[0]) <= {"W", "D"})
            self.assertTrue(set(grid[-1]) <= {"W", "D"})


class TestCastleBuilds(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        # plant the castle's overworld footprint so build() attaches it
        self.loc = Location("Bloodstone Castle", "A great fortress.",
                            10, 10, 8, 8)
        self.engine.world.locations.append(self.loc)
        self.builder = StructureBuilder(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_build_attaches_and_links_the_levels(self):
        self.builder.build()
        ground = self.engine.interiors.get("Bloodstone Castle")
        self.assertIsNotNone(ground, "the great hall is the entry")
        self.assertEqual(ground.structure_id, "bloodstone_castle")
        # descend the whole chain — five levels deep to the crypt
        depth, z = 1, ground
        while getattr(z, "level_below", None) is not None:
            z = z.level_below
            depth += 1
        self.assertEqual(depth, 5, "you can descend to the crypt")
        self.assertIn("Crypt", z.name)

    def test_the_great_hall_has_a_throne_inscription_and_loot(self):
        self.builder.build()
        hall = self.engine.interiors["Bloodstone Castle"]
        insc = [f for f in hall.furniture if f["name"] == "Inscription"]
        self.assertTrue(any("Throne" in f.get("text", "") for f in insc))
        self.assertTrue(any(f["name"] == "Chest" for f in hall.furniture))

    def test_the_crypt_is_dark_and_guarded(self):
        self.builder.build()
        z = self.engine.interiors["Bloodstone Castle"]
        while getattr(z, "level_below", None) is not None:
            z = z.level_below           # to the crypt
        self.assertTrue(z.dark, "the crypt is lightless")
        spawned = self.builder.on_enter_level(z)
        self.assertGreaterEqual(spawned, 1, "the dead keep watch")

    def test_the_crown_waits_in_the_crypt(self):
        self.builder.build()
        z = self.engine.interiors["Bloodstone Castle"]
        while getattr(z, "level_below", None) is not None:
            z = z.level_below
        chest = next(f for f in z.furniture if f["name"] == "Chest")
        key = f"bloodstone_castle:{chest['x']}:{chest['y']}"
        names = [getattr(i, "name", "") for i in
                 self.builder.chest_contents.get(key, [])]
        self.assertTrue(any("Crown of Bloodstone" in n for n in names),
                        "the legendary crown is the crypt's prize")

    def test_from_the_hall_you_climb_the_keep_and_descend_the_dungeon(self):
        # P18.3 floor-based linking: the ground (great hall) branches BOTH
        # up (apartments -> battlements) and down (undercroft -> ... crypt)
        self.builder.build()
        hall = self.engine.interiors["Bloodstone Castle"]
        self.assertEqual(hall.floor, 0, "you enter at ground level")
        up = []
        z = hall
        while getattr(z, "level_above", None) is not None:
            z = z.level_above
            up.append(z.name)
        self.assertEqual(len(up), 2, "two storeys above the hall")
        self.assertIn("Battlements", up[-1])
        down = []
        z = hall
        while getattr(z, "level_below", None) is not None:
            z = z.level_below
            down.append(z.name)
        self.assertEqual(len(down), 4, "four floors of depth below")
        self.assertIn("Crypt", down[-1])

    def test_the_battlements_are_the_top_with_archer_ground(self):
        self.builder.build()
        z = self.engine.interiors["Bloodstone Castle"]
        while getattr(z, "level_above", None) is not None:
            z = z.level_above
        self.assertIn("Battlements", z.name)
        self.assertIsNone(z.level_above, "nothing above the wall-walk")
        self.assertIsNotNone(z.stairs_down, "you can climb back down")


if __name__ == "__main__":
    unittest.main()
