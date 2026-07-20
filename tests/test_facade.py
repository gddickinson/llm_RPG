"""BLD.4 — building facade doors: a real entrance chosen by building KIND
(panelled / planked / arched / double), with the lock-state colour preserved."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame
pygame.init()

from ui import facade
from ui.door_glyphs import DOOR_STATE_COLORS


class TestDoorStyle(unittest.TestCase):
    def test_style_per_kind(self):
        cases = {
            "home": "panelled", "house": "panelled", "shop": "panelled",
            "smithy": "planked", "forge": "planked", "barn": "planked",
            "temple": "arched", "chapel": "arched", "library": "arched",
            "hall": "double", "inn": "double", "keep": "double",
            "": "panelled",
        }
        for kind, style in cases.items():
            self.assertEqual(facade.door_style_for(kind), style, kind)


class TestDoorShapes(unittest.TestCase):
    def _s(self, style):
        return facade.door_shapes(0, 0, 16, 24, style)

    def test_every_door_has_frame_and_step(self):
        for style in ("panelled", "planked", "arched", "double"):
            s = self._s(style)
            self.assertIn("lintel", s)
            self.assertIn("step", s)
            self.assertEqual(len(s["jambs"]), 2)

    def test_planked_has_planks_studs_brace(self):
        s = self._s("planked")
        self.assertTrue(s["planks"] and s["studs"] and s["brace"])

    def test_arched_and_double_have_arch(self):
        self.assertGreater(self._s("arched")["arch_r"], 0)
        self.assertEqual(len(self._s("double")["leaves"]), 2)

    def test_panelled_has_four_panels(self):
        self.assertEqual(len(self._s("panelled")["panels"]), 4)


class TestDrawDoor(unittest.TestCase):
    def _draw(self, kind, state):
        surf = pygame.Surface((48, 48))
        surf.fill((150, 120, 86))
        facade.draw_door(surf, 0, 0, 48, kind, state)
        return surf

    def test_draws_all_states_without_error(self):
        for kind in ("home", "smithy", "temple", "hall"):
            for state in ("open", "closed", "locked", "broken"):
                self._draw(kind, state)

    def test_lock_state_colour_is_used(self):
        # the closed and open doors differ, and the leaf carries the state hue
        closed = pygame.image.tostring(self._draw("home", "closed"), "RGB")
        openx = pygame.image.tostring(self._draw("home", "open"), "RGB")
        self.assertNotEqual(closed, openx)
        # the closed colour appears somewhere on the closed door
        want = DOOR_STATE_COLORS["closed"]
        surf = self._draw("home", "closed")
        found = any(surf.get_at((x, y))[:3] == want
                    for x in range(48) for y in range(48))
        self.assertTrue(found, "the closed-state colour paints the leaf")


class TestShopfront(unittest.TestCase):
    def test_shopfront_per_kind(self):
        self.assertIn("awning", facade.shopfront_for("tavern"))
        self.assertEqual(facade.shopfront_for("tavern")["sign"], "mug")
        self.assertTrue(facade.shopfront_for("smithy").get("forge"))
        self.assertEqual(facade.shopfront_for("smithy")["sign"], "anvil")
        self.assertTrue(facade.shopfront_for("shop").get("display"))
        self.assertTrue(facade.shopfront_for("bakery").get("oven"))

    def test_plain_home_has_no_shopfront(self):
        self.assertEqual(facade.shopfront_for("home"), {})
        self.assertEqual(facade.shopfront_for("temple"), {})
        self.assertEqual(facade.shopfront_for(""), {})

    def test_draw_shopfront_all_kinds_no_crash(self):
        for kind in ("tavern", "inn", "shop", "stall", "bakery", "smithy",
                     "forge", "home", "temple"):
            surf = pygame.Surface((64, 64))
            surf.fill((150, 120, 86))
            facade.draw_shopfront(surf, 0, 0, 64, kind)

    def test_shopfront_paints_something_for_a_shop(self):
        blank = pygame.Surface((64, 64))
        blank.fill((150, 120, 86))
        painted = blank.copy()
        facade.draw_shopfront(painted, 0, 0, 64, "tavern")
        self.assertNotEqual(pygame.image.tostring(blank, "RGB"),
                            pygame.image.tostring(painted, "RGB"))
        # a plain home paints nothing
        home = blank.copy()
        facade.draw_shopfront(home, 0, 0, 64, "home")
        self.assertEqual(pygame.image.tostring(blank, "RGB"),
                         pygame.image.tostring(home, "RGB"))


class TestIntegration(unittest.TestCase):
    def test_door_glyphs_renders_via_facade(self):
        # the glyph pass delegates to facade without crashing
        import os as _os
        import tempfile
        _os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                               tempfile.mkdtemp(prefix="llmrpg_fac_"))
        pygame.display.set_mode((320, 240))
        from engine.game_engine import GameEngine
        from ui.door_glyphs import draw_door_glyphs
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            target = pygame.Surface((320, 240))
            view = pygame.Rect(0, 0, 320, 240)
            draw_door_glyphs(target, e, view, 30, 30, 10, 10, 32)
        finally:
            try:
                e.end_game()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
