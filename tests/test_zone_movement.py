"""Zone-aware movement (P4.4b prerequisite #2).

Before this fix, movement inside dungeons/interiors consulted the
OVERWORLD grid: dungeon walls didn't block, and overworld water could
invisibly block a dungeon corridor.
"""

import unittest

from engine.game_engine import GameEngine
from world.dungeon import generate_dungeon
from world.world_map import TerrainType


class TestZoneMovement(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.dungeon = generate_dungeon(name="Move Test", seed=21)
        self.engine.current_dungeon = self.dungeon

    def tearDown(self):
        self.engine.current_dungeon = None
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _floor_next_to_wall(self):
        """A floor tile with a wall neighbor; returns (pos, wall_step)."""
        for y in range(1, self.dungeon.height - 1):
            for x in range(1, self.dungeon.width - 1):
                if self.dungeon.terrain[y][x] != TerrainType.GRASS:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if self.dungeon.terrain[y + dy][x + dx] == \
                            TerrainType.MOUNTAIN:
                        return ((x, y), (dx, dy))
        return (None, None)

    def _floor_pair(self):
        """Two adjacent floor tiles."""
        for y in range(1, self.dungeon.height - 1):
            for x in range(1, self.dungeon.width - 2):
                if self.dungeon.terrain[y][x] == TerrainType.GRASS and \
                        self.dungeon.terrain[y][x + 1] == TerrainType.GRASS:
                    return (x, y)
        return None

    def test_dungeon_walls_block(self):
        pos, step = self._floor_next_to_wall()
        self.assertIsNotNone(pos)
        self.player.position = pos
        self.assertFalse(self.engine.move_player(*step))
        self.assertEqual(self.player.position, pos)

    def test_dungeon_floor_allows_movement(self):
        pos = self._floor_pair()
        self.assertIsNotNone(pos)
        self.player.position = pos
        self.assertTrue(self.engine.move_player(1, 0))
        self.assertEqual(self.player.position, (pos[0] + 1, pos[1]))

    def test_overworld_terrain_is_irrelevant_inside_zone(self):
        """A dungeon corridor must be walkable even where the OVERWORLD
        has water at the same coordinates."""
        pos = self._floor_pair()
        self.player.position = pos
        wmap = self.engine.world.map
        # Force overworld water under the corridor
        wmap.terrain[pos[1]][pos[0] + 1] = TerrainType.WATER
        self.assertTrue(self.engine.move_player(1, 0),
                        "zone floor must override overworld water")

    def test_zone_bounds_block(self):
        self.player.position = (0, 0)
        self.assertFalse(self.engine.move_player(-1, 0))
        self.assertFalse(self.engine.move_player(0, -1))

    def test_monster_blocks_tile(self):
        from world.monsters import build_monster
        pos = self._floor_pair()
        self.player.position = pos
        blocker = build_monster("goblin", (pos[0] + 1, pos[1]))
        self.engine.npc_manager.add_npc(blocker)
        self.assertFalse(self.engine.move_player(1, 0))

    def test_interior_walls_block_and_door_opens(self):
        self.engine.current_dungeon = None
        if not self.engine.interiors:
            self.skipTest("no interiors")
        interior = next(iter(self.engine.interiors.values()))
        self.engine.current_interior = interior
        # BUILDING border tiles block
        self.player.position = (1, 1)
        self.assertFalse(self.engine.move_player(-1, 0))
        # The door (ROAD tile) is passable
        dx, dy = interior.door
        # Stand next to the door if possible
        for sx, sy in ((dx - 1, dy), (dx + 1, dy), (dx, dy - 1),
                       (dx, dy + 1)):
            if 0 <= sx < interior.width and 0 <= sy < interior.height \
                    and interior.terrain[sy][sx] == TerrainType.GRASS:
                self.player.position = (sx, sy)
                self.assertTrue(
                    self.engine.move_player(dx - sx, dy - sy))
                self.engine.current_interior = None
                return
        self.skipTest("no floor tile adjacent to door")


if __name__ == "__main__":
    unittest.main()
