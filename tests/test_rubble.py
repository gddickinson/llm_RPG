"""Rubble depth + interior breach sync tests (P10.4)."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class TestRubble(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.td = self.engine.tile_damage
        self.wmap = self.engine.world.map
        self.player = self.engine.player
        self.ox, self.oy = self.wmap.width - 10, self.wmap.height - 8
        for y in range(self.oy - 2, self.oy + 4):
            for x in range(self.ox - 2, self.ox + 6):
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

    def test_collapse_leaves_shallow_rubble(self):
        self.wmap.terrain[self.oy][self.ox] = TerrainType.BUILDING
        while self.wmap.terrain[self.oy][self.ox] != \
                TerrainType.RUBBLE:
            self.td.damage_tile(self.ox, self.oy, 40, "siege")
        self.assertEqual(self.td.depth_at(self.ox, self.oy), 1,
                         "one collapse = clamberable breach")

    def test_deep_rubble_blocks_movement(self):
        self.td.add_rubble(self.ox + 1, self.oy, depth=3)
        self._put_player(self.ox, self.oy)
        moved = self.engine.player_actions.move(1, 0)
        self.assertFalse(moved)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("piled too high", log)

    def test_shallow_rubble_is_passable(self):
        self.td.add_rubble(self.ox + 1, self.oy, depth=1)
        self._put_player(self.ox, self.oy)
        self.assertTrue(self.engine.player_actions.move(1, 0))

    def test_clearing_moves_debris_never_deletes(self):
        self.td.add_rubble(self.ox, self.oy, depth=3)
        total_before = sum(self.td.rubble_depth.values())
        self._put_player(self.ox + 1, self.oy)
        msg = self.engine.pickup_item()      # E fallback clears
        self.assertIn("stone", msg.lower())
        self.assertEqual(sum(self.td.rubble_depth.values()),
                         total_before,
                         "debris is MOVED, never deleted")
        self.assertEqual(self.td.depth_at(self.ox, self.oy), 2)

    def test_fully_cleared_tile_is_grass_again(self):
        self.td.add_rubble(self.ox, self.oy, depth=1)
        self._put_player(self.ox + 1, self.oy)
        self.engine.pickup_item()
        self.assertEqual(self.wmap.terrain[self.oy][self.ox],
                         TerrainType.GRASS)
        # the layer went somewhere
        self.assertGreaterEqual(sum(self.td.rubble_depth.values()), 1)

    def test_exterior_breach_opens_the_interior_wall(self):
        loc = next(l for l in self.engine.world.locations
                   if "farmhouse" in l.name.lower()
                   and l.name in self.engine.interiors)
        # smash the west wall
        bx, by = loc.x, loc.y
        while self.wmap.terrain[by][bx] != TerrainType.RUBBLE:
            self.td.damage_tile(bx, by, 40, "siege")
        inter = self.engine.interiors[loc.name]
        self.engine.door_manager.door(loc.name)["state"] = "open"
        self._put_player(loc.x + loc.width // 2,
                         loc.y + loc.height)
        self.engine.player_actions.move(0, -1)   # in via the door
        self.assertIs(self.engine.current_interior, inter)
        holes = [(x, y) for y in range(inter.height)
                 for x in range(inter.width)
                 if inter.terrain[y][x] == TerrainType.RUBBLE]
        self.assertTrue(holes,
                        "the hole must go all the way through")
        # the hole is on the perimeter
        x, y = holes[0]
        self.assertTrue(x in (0, inter.width - 1) or
                        y in (0, inter.height - 1))
        self.engine.exit_building()

    def test_depths_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.td.add_rubble(self.ox, self.oy, depth=2)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="rubble")
            self.td.rubble_depth = {}
            self.assertTrue(sm.load(self.engine, name="rubble"))
            self.assertEqual(
                self.engine.tile_damage.depth_at(self.ox, self.oy),
                2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
