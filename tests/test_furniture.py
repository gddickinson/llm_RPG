"""Furniture function tests (P9A.2)."""

import unittest

from engine.game_engine import GameEngine
from engine.furniture import piece_near, interact
from items.item_registry import create_item


class TestFurniture(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.engine.world.time = 12 * 60

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _inside(self, fragment, piece_name):
        interior = next(i for i in self.engine.interiors.values()
                        if fragment in i.name.lower())
        self.engine.current_interior = interior
        piece = next(p for p in interior.furniture
                     if p["name"] == piece_name)
        self.player.position = (piece["x"], piece["y"])
        return interior, piece

    def test_nothing_outside(self):
        self.engine.current_interior = None
        self.assertIsNone(self.engine.use_furniture())

    def test_piece_near_is_adjacent_inclusive(self):
        interior, piece = self._inside("tavern", "Hearth")
        self.player.position = (piece["x"] + 1, piece["y"])
        self.assertIsNotNone(piece_near(interior,
                                        *self.player.position))
        self.player.position = (piece["x"] + 3, piece["y"])
        self.assertIsNone(piece_near(interior, *self.player.position))

    def test_bed_rest_heals_once_a_day(self):
        self._inside("riverside inn", "Bed")
        self.player.hp = 1
        msg = interact(self.engine)
        self.assertIn("rest", msg.lower())
        self.assertGreater(self.player.hp, 1)
        hp = self.player.hp
        msg = interact(self.engine)
        self.assertIn("already rested", msg)
        self.assertEqual(self.player.hp, hp)

    def test_hearth_cooks_raw_food(self):
        self._inside("tavern", "Hearth")
        self.player.inventory.append(create_item("raw_trout"))
        msg = interact(self.engine)
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("cooked_trout", ids, msg)
        self.assertNotIn("raw_trout", ids)

    def test_hearth_without_food_teaches(self):
        self._inside("tavern", "Hearth")
        msg = interact(self.engine)
        self.assertIn("Bring something raw", msg)

    def test_altar_prays_without_shrine_location(self):
        self._inside("temple", "Altar")
        msg = interact(self.engine)
        self.assertNotIn("no holy place", msg)
        self.assertTrue("pray" in msg.lower() or
                        "answers" in msg.lower(), msg)

    def test_shelves_surface_a_rumor_once_a_day(self):
        self.engine.world_director.rumors.append(
            "The fen has crowned a king of rot.")
        self._inside("library", "Shelves")
        msg = interact(self.engine)
        self.assertIn("king of rot", msg)
        msg = interact(self.engine)
        self.assertIn("read enough", msg)

    def test_rummage_pays_once_per_building_per_day(self):
        self._inside("tavern", "Barrel")
        gold = self.player.gold
        # count UNITS not slots — a rummaged stackable may merge (P25.1)
        units = lambda: sum(getattr(it, "quantity", 1)
                            for it in self.player.inventory)
        u0 = units()
        msg1 = interact(self.engine)
        gained = (self.player.gold > gold or units() > u0)
        self.assertTrue(gained, msg1)
        msg2 = interact(self.engine)
        self.assertIn("already been through", msg2)

    def test_flavor_pieces_speak(self):
        self._inside("durgan", "Anvil")
        msg = interact(self.engine)
        self.assertIn("[K]", msg)

    def test_hint_bar_advertises(self):
        from ui.hints import context_hints
        self._inside("riverside inn", "Bed")
        hints = " ".join(context_hints(self.engine))
        self.assertIn("bed", hints.lower())


if __name__ == "__main__":
    unittest.main()
