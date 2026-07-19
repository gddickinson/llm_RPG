"""The openable world-map screen (GAP.4): fog-respecting landmark list +
a headless draw, and the contextual M key (map away from a bank)."""

import unittest

import pygame

from engine.game_engine import GameEngine
from ui import world_map_screen as wm
from world.world_map import TerrainType


class TestWorldMapHelpers(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_terrain_color_covers_types(self):
        for t in (TerrainType.GRASS, TerrainType.WATER, TerrainType.MOUNTAIN):
            c = wm.terrain_color(t)
            self.assertEqual(len(c), 3)

    def test_notable_locations_respects_fog(self):
        # only EXPLORED landmarks appear; the tuple shape is stable
        locs = wm.notable_locations(self.engine)
        for entry in locs:
            self.assertEqual(len(entry), 5)
            x, y, name, major, waystone = entry
            self.assertTrue(name)
            from engine import discovery
            self.assertTrue(discovery.is_explored(self.engine, x, y))

    def test_notable_locations_grows_with_exploration(self):
        before = len(wm.notable_locations(self.engine))
        # reveal the whole map
        from engine import discovery
        wmap = self.engine.world.map
        try:
            mask = discovery._explored(self.engine)
            for y in range(wmap.height):
                for x in range(wmap.width):
                    mask.add((x, y))
        except Exception:
            self.skipTest("no explored mask")
        after = len(wm.notable_locations(self.engine))
        self.assertGreaterEqual(after, before)


class TestWorldMapDrawAndKey(unittest.TestCase):
    def _gui(self):
        pygame.display.init()
        pygame.display.set_mode((1024, 768))
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        return GameGUI(engine)

    def _key(self, code):
        return pygame.event.Event(pygame.KEYDOWN, key=code, unicode="")

    def test_m_opens_and_closes_the_map(self):
        gui = self._gui()
        gui.mode = "play"
        # not at a bank at spawn arrival tile → M opens the map
        gui.input_handler.handle_event(self._key(pygame.K_m))
        self.assertEqual(gui.mode, "worldmap")
        # a draw must not raise
        from ui.world_map_screen import draw_world_map
        draw_world_map(gui)
        # M closes it again
        gui.input_handler.handle_event(self._key(pygame.K_m))
        self.assertEqual(gui.mode, "play")
        gui.engine.end_game()

    def test_escape_closes_the_map(self):
        gui = self._gui()
        gui.show_world_map()
        self.assertEqual(gui.mode, "worldmap")
        gui.input_handler.handle_event(self._key(pygame.K_ESCAPE))
        self.assertEqual(gui.mode, "play")
        gui.engine.end_game()


if __name__ == "__main__":
    unittest.main()
