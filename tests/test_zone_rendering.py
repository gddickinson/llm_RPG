"""Alternate-map rendering (dungeons / interiors) — P4.4 prerequisite.

The renderer used to draw the overworld even while the player walked
dungeon-local coordinates, making dungeons and interiors unplayable
visually.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from engine.game_engine import GameEngine
from ui.renderer import MapRenderer


class TestZoneRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        cls.engine.start_game()
        cls.renderer = MapRenderer(tile_size=16)
        cls.surface = pygame.Surface((320, 240))
        cls.view = pygame.Rect(0, 0, 320, 240)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass
        pygame.quit()

    def tearDown(self):
        self.engine.current_dungeon = None
        self.engine.current_interior = None

    def test_no_zone_by_default(self):
        self.assertIsNone(MapRenderer.active_zone(self.engine))

    def test_dungeon_zone_detected_and_renders(self):
        from world.dungeon import generate_dungeon
        dungeon = generate_dungeon(name="Render Test", seed=7)
        self.engine.current_dungeon = dungeon
        self.assertIs(MapRenderer.active_zone(self.engine), dungeon)
        self.engine.player.position = dungeon.exit_pos
        self.renderer.render(self.surface, self.engine, self.view)

    def test_interior_zone_detected_and_renders(self):
        if not self.engine.interiors:
            self.skipTest("no interiors")
        interior = next(iter(self.engine.interiors.values()))
        self.engine.current_interior = interior
        self.assertIs(MapRenderer.active_zone(self.engine), interior)
        self.engine.player.position = interior.door
        self.renderer.render(self.surface, self.engine, self.view)

    def test_dungeon_render_differs_from_overworld(self):
        """The zone fix must actually change what's drawn."""
        self.engine.player.position = (10, 10)
        self.renderer.render(self.surface, self.engine, self.view)
        overworld_pixels = pygame.image.tostring(self.surface, "RGB")

        from world.dungeon import generate_dungeon
        dungeon = generate_dungeon(name="Diff Test", seed=11)
        self.engine.current_dungeon = dungeon
        self.engine.player.position = dungeon.exit_pos
        self.renderer.render(self.surface, self.engine, self.view)
        dungeon_pixels = pygame.image.tostring(self.surface, "RGB")

        self.assertNotEqual(overworld_pixels, dungeon_pixels,
                            "dungeon view must not show the overworld")

    def test_dungeon_monsters_drawn_only_in_bounds(self):
        from world.dungeon import generate_dungeon
        from world.monsters import build_monster
        dungeon = generate_dungeon(name="Mob Test", seed=13)
        self.engine.current_dungeon = dungeon
        self.engine.player.position = dungeon.exit_pos
        inside = build_monster("goblin", dungeon.rooms[-1].center())
        self.engine.npc_manager.add_npc(inside)
        # Should render without error with monsters present
        self.renderer.render(self.surface, self.engine, self.view)

    def test_small_interior_camera_clamps(self):
        """8x6 interior is smaller than the view — must not crash."""
        if not self.engine.interiors:
            self.skipTest("no interiors")
        interior = next(iter(self.engine.interiors.values()))
        self.engine.current_interior = interior
        self.engine.player.position = (1, 1)
        self.renderer.render(self.surface, self.engine, self.view)


if __name__ == "__main__":
    unittest.main()
