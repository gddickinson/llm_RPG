"""GX.2 — the teleport WAYSTONE renders as a raised, glowing DIAS (George: make
the platforms larger, on a raised dais, easy to see)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame
pygame.init()

from ui import dais


class TestDaisGeometry(unittest.TestCase):
    def test_tiers_are_stepped(self):
        tiers = dais.dais_tiers(0, 0, 48)
        self.assertEqual(len(tiers), 3)
        # inner tiers get NARROWER and sit HIGHER (smaller y) than outer ones
        widths = [t[2] for t in tiers]
        self.assertTrue(widths[0] > widths[1] > widths[2], widths)
        ys = [t[1] for t in tiers]
        self.assertTrue(ys[0] >= ys[1] >= ys[2], ys)

    def test_dais_is_bigger_than_the_tile(self):
        outer = dais.dais_tiers(0, 0, 48)[0]
        self.assertGreater(outer[2], 48, "the dais reads bigger than a tile")

    def test_rune_sits_on_the_top_tier(self):
        top = dais.dais_tiers(0, 0, 48)[-1]
        cx, cy, r = dais.rune_circle(0, 0, 48)
        self.assertTrue(top[0] <= cx <= top[0] + top[2])
        self.assertGreater(r, 0)


class TestDaisDraw(unittest.TestCase):
    def test_draw_dais_paints_stone_and_glow(self):
        surf = pygame.Surface((96, 96), pygame.SRCALPHA)
        dais.draw_dais(surf, 24, 24, 48, phase=0.25)
        painted = sum(1 for x in range(0, 96, 2) for y in range(0, 96, 2)
                      if surf.get_at((x, y))[3] > 0)
        self.assertGreater(painted, 50, "the dais draws stone + rune + glow")

    def test_draw_all_marks_waystones(self):
        import tempfile
        os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                              tempfile.mkdtemp(prefix="llmrpg_dais_"))
        pygame.display.set_mode((320, 240))
        from engine.game_engine import GameEngine
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            ways = [l for l in e.world.locations
                    if (l.properties or {}).get("waystone")]
            self.assertTrue(ways, "waystones seed")
            w = ways[0]
            target = pygame.Surface((320, 240))
            base = target.copy()
            view = pygame.Rect(0, 0, 320, 240)
            dais.draw_all(target, e, view, w.x - 3, w.y - 3, 32)
            self.assertNotEqual(pygame.image.tostring(target, "RGB"),
                                pygame.image.tostring(base, "RGB"),
                                "a dais is drawn at the waystone in view")
        finally:
            try:
                e.end_game()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
