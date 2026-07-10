"""Shadowcasting FOV tests (P8.6)."""

import unittest

from world.fov import (compute_fov, has_line_of_sight, zone_fov,
                       overworld_los)


def _grid_opaque(walls):
    return lambda x, y: (x, y) in walls


class TestShadowcasting(unittest.TestCase):
    def test_open_field_is_circular(self):
        fov = compute_fov(10, 10, 4, _grid_opaque(set()), 21, 21)
        self.assertIn((10, 10), fov)
        self.assertIn((14, 10), fov)
        self.assertIn((10, 6), fov)
        self.assertNotIn((15, 10), fov, "beyond radius")
        self.assertNotIn((14, 14), fov, "circular, not square")

    def test_a_wall_throws_a_shadow(self):
        walls = {(12, 10)}
        fov = compute_fov(10, 10, 6, _grid_opaque(walls), 21, 21)
        self.assertIn((12, 10), fov, "the wall itself is seen")
        self.assertNotIn((13, 10), fov, "behind it is not")
        self.assertNotIn((14, 10), fov)
        self.assertIn((13, 13), fov, "off-axis stays visible")

    def test_a_wall_segment_shadows_a_cone(self):
        walls = {(12, 9), (12, 10), (12, 11)}
        fov = compute_fov(10, 10, 8, _grid_opaque(walls), 21, 21)
        for x in range(13, 18):
            self.assertNotIn((x, 10), fov)

    def test_line_of_sight_both_ways(self):
        walls = {(12, 10)}
        opaque = _grid_opaque(walls)
        self.assertFalse(has_line_of_sight(10, 10, 14, 10, opaque,
                                           21, 21))
        self.assertTrue(has_line_of_sight(10, 10, 11, 10, opaque,
                                          21, 21))
        self.assertFalse(has_line_of_sight(14, 10, 10, 10, opaque,
                                           21, 21),
                         "symmetric: they can't see you either")

    def test_out_of_radius_is_never_visible(self):
        self.assertFalse(has_line_of_sight(0, 0, 20, 0,
                                           _grid_opaque(set()),
                                           30, 30, max_radius=12))


class TestGameIntegration(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_buildings_block_overworld_los(self):
        loc = next(l for l in self.engine.world.locations
                   if l.name in self.engine.interiors
                   and l.width >= 2)
        west = (loc.x - 1, loc.y)
        east = (loc.x + loc.width, loc.y)
        wmap = self.engine.world.map
        if not (0 <= west[0] and east[0] < wmap.width):
            self.skipTest("building at map edge")
        self.assertFalse(overworld_los(self.engine, west, east),
                         "a building must block sight across it")

    def test_open_ground_has_los(self):
        wmap = self.engine.world.map
        a = (wmap.width - 3, wmap.height - 3)
        b = (wmap.width - 7, wmap.height - 3)
        from world.world_map import TerrainType
        for x in range(wmap.width - 7, wmap.width - 2):
            wmap.terrain[wmap.height - 3][x] = TerrainType.GRASS
        self.assertTrue(overworld_los(self.engine, a, b))

    def test_ranged_shot_refused_through_a_wall(self):
        from world.monsters import build_monster
        from items.item_registry import create_item
        from characters.equipment import equip
        loc = next(l for l in self.engine.world.locations
                   if l.name in self.engine.interiors
                   and l.width >= 2 and l.x > 1
                   and l.x + l.width < self.engine.world.map.width - 1)
        wmap = self.engine.world.map
        player = self.engine.player
        wmap.remove_character(player)
        player.position = (loc.x - 1, loc.y)
        wmap.place_character(player, *player.position)
        wolf = build_monster("wolf", (loc.x + loc.width, loc.y))
        self.engine.npc_manager.add_npc(wolf)
        wmap.place_character(wolf, *wolf.position)
        bow = create_item("bow")
        player.inventory.append(bow)
        equip(player, bow)
        arrows = create_item("arrow")
        if arrows is not None:
            arrows.quantity = 5
            player.inventory.append(arrows)
        msg = self.engine.shoot_ranged(wolf.name)
        self.assertIn("No clear shot", msg)

    def test_dungeon_fov_computes(self):
        from world.dungeon import generate_dungeon
        from world.fov import zone_fov
        dungeon = generate_dungeon(seed=3)
        room = dungeon.rooms[0]
        cx = room.x + room.w // 2
        cy = room.y + room.h // 2
        fov = zone_fov(dungeon, (cx, cy), radius=8)
        self.assertIn((cx, cy), fov)
        self.assertGreater(len(fov), 4,
                           "a room center should see the room")
        self.assertLess(len(fov), dungeon.width * dungeon.height,
                        "walls must hide most of the dungeon")


if __name__ == "__main__":
    unittest.main()
