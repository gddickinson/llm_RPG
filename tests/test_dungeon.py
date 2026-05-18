"""Tests for procedural dungeons."""

import unittest

from engine.game_engine import GameEngine
from world.dungeon import generate_dungeon, populate_dungeon
from world.world_map import TerrainType


class TestDungeonGeneration(unittest.TestCase):
    def test_basic_shape(self):
        d = generate_dungeon(seed=1)
        self.assertEqual(len(d.terrain), d.height)
        self.assertEqual(len(d.terrain[0]), d.width)

    def test_has_rooms_and_corridors(self):
        d = generate_dungeon(seed=1)
        self.assertGreater(len(d.rooms), 0)
        # Some floor tiles exist
        floor_count = sum(
            1 for row in d.terrain for t in row
            if t == TerrainType.GRASS)
        self.assertGreater(floor_count, 10)

    def test_exit_is_walkable(self):
        d = generate_dungeon(seed=1)
        ex, ey = d.exit_pos
        self.assertIn(d.terrain[ey][ex],
                      (TerrainType.ROAD, TerrainType.GRASS))

    def test_determinism(self):
        a = generate_dungeon(seed=42)
        b = generate_dungeon(seed=42)
        self.assertEqual(a.terrain, b.terrain)


class TestDungeonEntry(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _find_cave(self):
        wmap = self.engine.world.map
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.terrain[y][x] == TerrainType.CAVE:
                    return (x, y)
        return None

    def test_enter_cave(self):
        spot = self._find_cave()
        if not spot:
            self.skipTest("no cave generated")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = spot
        self.engine.world.map.place_character(
            self.engine.player, *spot)
        msg = self.engine.enter_dungeon()
        self.assertIn("descend", msg.lower())
        self.assertIsNotNone(self.engine.current_dungeon)

    def test_exit_returns_to_overworld(self):
        spot = self._find_cave()
        if not spot:
            self.skipTest("no cave generated")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = spot
        self.engine.world.map.place_character(
            self.engine.player, *spot)
        self.engine.enter_dungeon()
        msg = self.engine.exit_dungeon()
        self.assertIn("emerge", msg.lower())
        self.assertIsNone(self.engine.current_dungeon)
        self.assertEqual(self.engine.player.position, spot)

    def test_cannot_enter_non_cave(self):
        # Move to a clearly non-cave tile
        for y in range(self.engine.world.map.height):
            for x in range(self.engine.world.map.width):
                if self.engine.world.map.terrain[y][x] == TerrainType.GRASS:
                    self.engine.player.position = (x, y)
                    msg = self.engine.enter_dungeon()
                    self.assertIn("no cave", msg.lower())
                    return


if __name__ == "__main__":
    unittest.main()
