"""Tests for the building blueprint library."""

import unittest

from world.blueprints import (
    Blueprint, BLUEPRINT_LIBRARY, blueprint_for_location, CELL_NAME,
)


class TestBlueprint(unittest.TestCase):
    def test_dimensions_inferred(self):
        bp = Blueprint(name="X", kind="x", grid=[
            list("WWW"), list("WFW"), list("WDW"),
        ])
        self.assertEqual(bp.width, 3)
        self.assertEqual(bp.height, 3)

    def test_doors_and_floors(self):
        bp = BLUEPRINT_LIBRARY["tavern"]
        doors = bp.door_positions()
        floors = bp.floor_positions()
        self.assertEqual(len(doors), 1)
        self.assertGreater(len(floors), 0)

    def test_furniture_listed(self):
        bp = BLUEPRINT_LIBRARY["forge"]
        items = bp.furniture()
        self.assertTrue(items)
        # Each entry: (code, x, y)
        for c, x, y in items:
            self.assertNotIn(c, ("W", "F", "D", "."))

    def test_rotation(self):
        bp = BLUEPRINT_LIBRARY["forge"]
        rot = bp.rotated()
        # Rotated 90deg cw: new width == old height
        self.assertEqual(rot.width, bp.height)
        self.assertEqual(rot.height, bp.width)
        self.assertEqual(rot.name, bp.name)

    def test_lookup_by_name(self):
        # Specific names
        self.assertIsNotNone(blueprint_for_location("Oakvale Tavern"))
        self.assertIsNotNone(blueprint_for_location("Durgan's Forge"))
        self.assertIsNotNone(blueprint_for_location("Temple of Light"))
        self.assertIsNotNone(blueprint_for_location("Riverside Inn"))
        self.assertIsNotNone(blueprint_for_location("Hamlet Chapel"))
        self.assertIsNotNone(blueprint_for_location("Foreman's Hall"))
        self.assertIsNotNone(blueprint_for_location("Stonepine Smithy"))
        self.assertIsNotNone(blueprint_for_location("Wheelwright's Shop"))
        self.assertIsNone(blueprint_for_location("Wilderness"))

    def test_cell_name_map(self):
        # Every recognized furniture code has a human name
        for code in "TBACPRS":
            self.assertIn(code, CELL_NAME)


class TestInteriorsUseBlueprints(unittest.TestCase):
    def test_interior_built_from_blueprint(self):
        from engine.game_engine import GameEngine
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            inter = e.interiors.get("Oakvale Tavern")
            self.assertIsNotNone(inter)
            # GX.3 SCALE-UP: a 2x2 footprint now opens into a roomy 10x10
            self.assertGreaterEqual(inter.width, 10)
            self.assertGreaterEqual(inter.height, 10)
            # Has furniture (table, hearth, etc.)
            self.assertTrue(inter.furniture)
        finally:
            e.end_game()


if __name__ == "__main__":
    unittest.main()
