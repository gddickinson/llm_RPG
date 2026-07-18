"""P34.19 — physical effects: fire/wet overlays, the launch + fx-decay hooks,
and the thrown/flail clips."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_fx_"))

import unittest
import pygame
pygame.init()


class _Char:
    def __init__(self, meta=None):
        self.metadata = meta or {}
        self.position = (5, 5)


class TestOverlays(unittest.TestCase):
    def test_fire_and_wet_draw_without_crashing(self):
        from ui import char_fx
        surf = pygame.Surface((96, 144), pygame.SRCALPHA)
        char_fx.draw_effects(surf, _Char({"_fx_fire": 3}), 20, 30, 48, 0.3)
        char_fx.draw_effects(surf, _Char({"_fx_wet": 4}), 20, 30, 48, 0.7)

    def test_no_effect_draws_nothing(self):
        from ui import char_fx
        surf = pygame.Surface((96, 144), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        char_fx.draw_effects(surf, _Char({}), 20, 30, 48, 0.3)
        self.assertEqual(int(pygame.surfarray.array_alpha(surf).sum()), 0)


class TestClips(unittest.TestCase):
    def test_launched_and_flail_registered(self):
        from ui import char_clips as cc
        from ui.char_pose import build_pose
        for a in ("launched", "flail"):
            self.assertIn(a, cc._CLIPS)
            p = build_pose(60, 200, 80, 0, 0, False, 0, (1, 0),
                           {"shoulder": 1, "hip": 1, "head": 1, "girth": 1, "h": 1})
            out = cc.apply(a, p, 0.5, 80, (1, 0))
            self.assertIn("head", out)


class TestEngineHooks(unittest.TestCase):
    def test_launch_sets_the_thrown_emote(self):
        from engine import anim
        c = _Char()
        anim.launch(c)
        self.assertEqual(c.metadata.get("_emote"), "launched")

    def test_update_fx_decays_and_clears(self):
        from engine import anim

        class _NPCMgr:
            npcs = {}

        class _Eng:
            def __init__(self):
                self.player = _Char({"_fx_fire": 2, "_fx_wet": 1})
                self.npc_manager = _NPCMgr()
        e = _Eng()
        anim.update_fx(e)
        self.assertEqual(e.player.metadata.get("_fx_fire"), 1)
        self.assertNotIn("_fx_wet", e.player.metadata)     # 1 → 0 → removed
        anim.update_fx(e)
        self.assertNotIn("_fx_fire", e.player.metadata)


class TestStatusOverlays(unittest.TestCase):
    """H5 — magical conditions shown on the body (aura / wisps)."""

    def test_status_fx_table(self):
        from ui import char_fx
        names = [n for n, _, _ in char_fx._STATUS_FX]
        self.assertIn("blessed", names)
        self.assertIn("poisoned", names)
        self.assertIn("cursed", names)

    def test_aura_and_wisps_draw_pixels(self):
        import pygame
        from ui import char_fx
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        char_fx._aura(surf, 60, 60, 64, 0.4, (255, 224, 130))
        char_fx._wisps(surf, 60, 60, 64, 0.4, (96, 205, 96))
        self.assertGreater(pygame.mask.from_surface(surf, 5).count(), 10)

    def test_draw_status_haloes_a_blessed_char(self):
        import pygame
        from ui import char_fx

        class _C:
            def __init__(self):
                self.metadata = {"status_effects": [{"name": "blessed"}]}
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        char_fx.draw_status(surf, _C(), 60, 60, 64, 0.4)
        self.assertGreater(pygame.mask.from_surface(surf, 5).count(), 0,
                           "a blessed body shows a halo")


if __name__ == "__main__":
    unittest.main()
