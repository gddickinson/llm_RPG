"""Multi-level building tests (P9A.5)."""

import unittest

from engine.game_engine import GameEngine


class TestMultiLevel(unittest.TestCase):
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

    def _interior(self, fragment):
        return next(i for name, i in self.engine.interiors.items()
                    if fragment in name.lower())

    def _go_inside(self, inter):
        self.engine.current_interior = inter
        self.engine.exterior_return_pos = (5, 5)
        self.player.position = inter.door

    def test_taverns_have_bedrooms_upstairs(self):
        tavern = self._interior("tavern")
        self.assertIsNotNone(tavern.level_above)
        loft = tavern.level_above
        self.assertFalse(loft.ground)
        self.assertIs(loft.level_below, tavern)
        names = [f["name"] for f in loft.furniture]
        self.assertIn("Bed", names)
        self.assertIn("Stairs down", names)

    def test_shops_have_cellars(self):
        shop = self._interior("store")
        self.assertIsNotNone(shop.level_below)
        cellar = shop.level_below
        names = [f["name"] for f in cellar.furniture]
        self.assertIn("Barrel", names)
        self.assertIn("Stairs up", names)

    def test_stairs_are_twinned(self):
        tavern = self._interior("tavern")
        self.assertEqual(tavern.stairs_up,
                         tavern.level_above.stairs_down)

    def test_stepping_onto_stairs_climbs(self):
        tavern = self._interior("tavern")
        self._go_inside(tavern)
        sx, sy = tavern.stairs_up
        self.player.position = (sx - 1, sy) if sx > 1 else (sx + 1, sy)
        dx = sx - self.player.position[0]
        moved = self.engine.player_actions.move(dx, 0)
        self.assertTrue(moved)
        self.assertIs(self.engine.current_interior,
                      tavern.level_above)
        self.assertEqual(self.player.position, tavern.stairs_up)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("climb the stairs", log)

    def test_descending_returns_to_the_taproom(self):
        tavern = self._interior("tavern")
        loft = tavern.level_above
        self.engine.current_interior = loft
        sx, sy = loft.stairs_down
        self.player.position = (sx - 1, sy) if sx > 1 else (sx + 1, sy)
        dx = sx - self.player.position[0]
        self.engine.player_actions.move(dx, 0)
        self.assertIs(self.engine.current_interior, tavern)

    def test_tab_upstairs_descends_instead_of_exiting(self):
        tavern = self._interior("tavern")
        self._go_inside(tavern)
        self.engine.current_interior = tavern.level_above
        msg = self.engine.exit_building()
        self.assertIn("ground floor", msg)
        self.assertIs(self.engine.current_interior, tavern)
        self.assertEqual(self.player.position, tavern.stairs_up)

    def test_tab_on_ground_floor_exits(self):
        tavern = self._interior("tavern")
        self._go_inside(tavern)
        msg = self.engine.exit_building()
        self.assertIn("leave", msg.lower())
        self.assertIsNone(self.engine.current_interior)

    def test_upstairs_beds_are_restable(self):
        from engine.furniture import interact
        tavern = self._interior("tavern")
        loft = tavern.level_above
        self.engine.current_interior = loft
        bed = next(f for f in loft.furniture if f["name"] == "Bed")
        self.player.position = (bed["x"], bed["y"])
        self.player.hp = 1
        msg = interact(self.engine)
        self.assertIn("rest", msg.lower())
        self.assertGreater(self.player.hp, 1)

    def test_cellar_rummage_works(self):
        from engine.furniture import interact
        shop = self._interior("store")
        cellar = shop.level_below
        self.engine.current_interior = cellar
        barrel = next(f for f in cellar.furniture
                      if f["name"] == "Barrel")
        self.player.position = (barrel["x"], barrel["y"])
        gold = self.player.gold
        n_items = len(self.player.inventory)
        interact(self.engine)
        self.assertTrue(self.player.gold > gold or
                        len(self.player.inventory) > n_items)


if __name__ == "__main__":
    unittest.main()
