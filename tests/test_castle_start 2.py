"""'Begin at the Castle' (P18.5): a start that plants the Bloodstone realm
and drops the newly-made hero at the castle gate."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from world.castle_region import CASTLE_NAME, TOWN_NAME, VILLAGES
from world.world_map import TerrainType


class TestCastleStart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False,
                                world_kind="castle")
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_the_realm_is_the_castle_region(self):
        names = {l.name for l in self.engine.world.locations}
        self.assertIn(CASTLE_NAME, names)
        self.assertIn(TOWN_NAME, names)
        for v in VILLAGES:
            self.assertIn(v, names)

    def test_the_hero_stands_at_the_gate_on_open_ground(self):
        px, py = self.engine.player.position
        terr = self.engine.world.map.terrain[py][px]
        self.assertNotEqual(terr, TerrainType.BUILDING,
                            "you don't spawn inside a wall")
        castle = next(l for l in self.engine.world.locations
                      if l.name == CASTLE_NAME)
        # just outside the south wall, near the gatehouse
        self.assertLessEqual(abs(px - (castle.x + castle.width // 2)), 2)
        self.assertGreaterEqual(py, castle.y)

    def test_the_seven_floor_keep_is_attached(self):
        hall = self.engine.interiors.get(CASTLE_NAME)
        self.assertIsNotNone(hall)
        self.assertEqual(hall.structure_id, "bloodstone_castle")


class TestDefaultUnaffected(unittest.TestCase):
    def test_the_default_start_is_still_oakvale(self):
        eng = GameEngine(llm_provider="heuristic",
                         enable_npc_processes=False)   # world_kind default
        eng.start_game()
        try:
            names = {l.name for l in eng.world.locations}
            self.assertIn("Oakvale Village", names)
            self.assertNotIn(CASTLE_NAME, names)
        finally:
            eng.end_game()


class TestMenuRouting(unittest.TestCase):
    def _menu(self):
        import pygame
        from ui.start_menu import StartMenu
        pygame.display.init()
        return StartMenu(width=800, height=600)

    def test_the_castle_option_is_on_the_new_game_menu(self):
        from ui.start_menu import NEW_GAME_OPTIONS
        codes = [c for _, c in NEW_GAME_OPTIONS]
        self.assertIn("castle", codes)

    def test_choosing_the_castle_routes_through_creation_with_the_flag(self):
        import pygame
        from ui.start_menu import NEW_GAME_OPTIONS

        class _Ev:
            type = pygame.KEYDOWN
            key = pygame.K_RETURN

        menu = self._menu()
        menu.state = "new_game"
        menu.selected = [c for _, c in NEW_GAME_OPTIONS].index("castle")
        menu._newgame_key(pygame.K_RETURN)
        self.assertEqual(menu.pending_start, "castle")
        self.assertEqual(menu.state, "customize", "you still make a hero")
        # finishing character creation carries the castle start out
        menu.creator = MagicMock()
        menu.creator.handle_key.return_value = True
        menu.creator.build_spec.return_value = "SPEC"
        result = menu._handle_key(_Ev())
        self.assertEqual(result,
                         {"action": "new", "spec": "SPEC", "start": "castle"})
        self.assertEqual(menu.pending_start, "default", "flag resets")


if __name__ == "__main__":
    unittest.main()
