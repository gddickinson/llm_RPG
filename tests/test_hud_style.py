"""HUD styling (P15.3): prefix-coloured log + minimap fog of war."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from ui import hud_style                              # noqa: E402
from ui.hud_style import (line_color, dim, fog_terrain_color,
                          PREFIX_COLORS, CATEGORY_COLORS, UNSEEN,
                          DEFAULT_LOG)                # noqa: E402


class TestLineColor(unittest.TestCase):
    def test_iconic_prefixes(self):
        self.assertEqual(line_color("[!] the ground blackens"),
                         PREFIX_COLORS["[!]"])
        self.assertEqual(line_color("[Law] a bounty on your head"),
                         PREFIX_COLORS["[Law]"])
        self.assertEqual(line_color("[DM] a cold wind rises"),
                         PREFIX_COLORS["[DM]"])
        self.assertEqual(line_color("[Home] the shack is yours"),
                         PREFIX_COLORS["[Home]"])

    def test_leading_whitespace_is_tolerated(self):
        self.assertEqual(line_color("   [Law] fine"), PREFIX_COLORS["[Law]"])

    def test_unprefixed_falls_back_to_category(self):
        # a foe's blow (not "you ...") -> combat orange
        self.assertEqual(line_color("The troll strikes you"),
                         CATEGORY_COLORS["combat"])
        # your own deliberate act -> neutral player colour
        self.assertEqual(line_color("You walk to the market"),
                         CATEGORY_COLORS["player"])
        # ambient chatter -> dim
        self.assertEqual(line_color("The wolf wanders off"),
                         CATEGORY_COLORS["ambient"])

    def test_bad_input_is_safe(self):
        self.assertEqual(line_color(None), DEFAULT_LOG)
        self.assertEqual(line_color(12345), DEFAULT_LOG)

    def test_every_colour_is_valid_rgb(self):
        for col in list(PREFIX_COLORS.values()) + \
                list(CATEGORY_COLORS.values()):
            self.assertEqual(len(col), 3)
            self.assertTrue(all(0 <= c <= 255 for c in col))


class TestDimAndFog(unittest.TestCase):
    def test_dim_scales_toward_black(self):
        self.assertEqual(dim((200, 100, 50), 0.5), (100, 50, 25))
        self.assertEqual(dim((255, 255, 255), 0.0), (0, 0, 0))

    def test_dim_ignores_alpha(self):
        self.assertEqual(dim((200, 100, 50, 255), 1.0), (200, 100, 50))

    def test_fog_states(self):
        base = (90, 150, 70)
        self.assertEqual(fog_terrain_color(base, True, True), base)
        self.assertEqual(fog_terrain_color(base, True, False), base)
        self.assertEqual(fog_terrain_color(base, False, True), dim(base))
        self.assertEqual(fog_terrain_color(base, False, False), UNSEEN)

    def test_explored_is_dimmer_than_visible_but_brighter_than_unseen(self):
        base = (200, 200, 200)
        vis = sum(fog_terrain_color(base, True, True))
        exp = sum(fog_terrain_color(base, False, True))
        uns = sum(fog_terrain_color(base, False, False))
        self.assertGreater(vis, exp)
        self.assertGreater(exp, uns)


class TestMinimapFog(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_fog_none_when_nothing_seen(self):
        from ui.hud import _minimap_fog
        self.engine._visible_tiles = set()
        self.engine.player.metadata["explored"] = []
        self.assertIsNone(_minimap_fog(self.engine))

    def test_fog_reports_seen_sets(self):
        from ui.hud import _minimap_fog
        self.engine._visible_tiles = {(1, 1), (2, 1)}
        self.engine.player.metadata["explored"] = [(1, 1), (2, 1), (3, 1)]
        fog = _minimap_fog(self.engine)
        self.assertIsNotNone(fog)
        vis, exp = fog
        self.assertIn((1, 1), vis)
        self.assertIn((3, 1), exp)


class TestHudSmoke(unittest.TestCase):
    def test_log_and_minimap_render_without_crashing(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 240))
        from ui.hud import HUD
        from engine.game_engine import GameEngine
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        # a spread of prefixes to colour
        for line in ("[!] danger", "[Law] bounty", "[DM] a portent",
                     "You draw your sword", "The troll strikes you"):
            engine.memory_manager.add_event(line)
        hud = HUD()
        surf = pygame.Surface((320, 240))
        hud.draw_event_log(surf, engine, pygame.Rect(0, 0, 200, 200))
        hud.draw_minimap(surf, engine, pygame.Rect(0, 0, 160, 160))
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
