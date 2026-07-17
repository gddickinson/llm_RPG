"""P41.3 — the isometric world render path (behind the toggle)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_iso_"))

import unittest

import pygame

from ui import iso_render


class TestToggle(unittest.TestCase):
    def setUp(self):
        self._prev = _os.environ.get("LLM_RPG_RENDER")

    def tearDown(self):
        if self._prev is None:
            _os.environ.pop("LLM_RPG_RENDER", None)
        else:
            _os.environ["LLM_RPG_RENDER"] = self._prev

    def test_env_toggle(self):
        _os.environ["LLM_RPG_RENDER"] = "iso"
        self.assertTrue(iso_render.iso_enabled())
        _os.environ["LLM_RPG_RENDER"] = "topdown"
        self.assertFalse(iso_render.iso_enabled())
        _os.environ.pop("LLM_RPG_RENDER", None)
        self.assertFalse(iso_render.iso_enabled())


class TestRenderIso(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_iso_frame_draws_without_error_and_paints(self):
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        view = pygame.Rect(0, 0, 640, 480)
        iso_render.render_iso(surf, self.engine, view, 48)
        painted = sum(1 for x in range(0, 640, 12) for y in range(0, 480, 12)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 40, "the iso world should fill the view")

    def test_origin_centres_the_player(self):
        view = pygame.Rect(0, 0, 640, 480)
        iso = iso_render._projection(48)
        origin = iso_render._origin(iso, self.engine, view)
        px, py = self.engine.player.position
        z = iso_render._HEIGHT.get(
            iso_render._terrain_name(self.engine.world.map.terrain[py][px]), 0)
        sx, sy = iso.world_to_screen(px, py, z, origin)
        # the player projects to (roughly) the middle of the view
        self.assertAlmostEqual(sx, 320, delta=2)
        self.assertAlmostEqual(sy, 240, delta=2)

    def test_terrain_relief_lifts_mountains_sinks_water(self):
        self.assertGreater(iso_render._HEIGHT["mountain"], 0)
        self.assertLess(iso_render._HEIGHT["water"], 0)

    def test_renderer_setting_toggles_iso(self):        # P41.7 in-game toggle
        from engine import settings
        _os.environ.pop("LLM_RPG_RENDER", None)
        settings.set_setting(self.engine.player, "renderer", "topdown")
        self.assertFalse(iso_render.iso_enabled(self.engine))
        settings.set_setting(self.engine.player, "renderer", "iso")
        self.assertTrue(iso_render.iso_enabled(self.engine))
        settings.set_setting(self.engine.player, "renderer", "topdown")

    def test_env_overrides_the_setting(self):
        from engine import settings
        settings.set_setting(self.engine.player, "renderer", "iso")
        _os.environ["LLM_RPG_RENDER"] = "topdown"
        try:
            self.assertFalse(iso_render.iso_enabled(self.engine))
        finally:
            _os.environ.pop("LLM_RPG_RENDER", None)
            settings.set_setting(self.engine.player, "renderer", "topdown")

    def test_draw_diamond_is_shaded_not_flat(self):        # P41.7 fidelity
        import pygame
        from ui.iso import IsoProjection
        surf = pygame.Surface((128, 128))
        surf.fill((0, 0, 0))
        iso_render.draw_diamond(surf, IsoProjection(64, 32, 16),
                                64, 64, (90, 150, 70), seed=7)
        shades = {surf.get_at((x, y))[:3]
                  for x in range(50, 78, 3) for y in range(54, 74, 3)}
        self.assertGreaterEqual(len(shades), 2, "the tile should be shaded")

    def test_gameplay_overlays_render_in_iso(self):        # P41.11 parity
        import types
        from items.item_registry import create_item
        eng = self.engine
        px, py = eng.player.position
        meta = eng.player.metadata.setdefault("explored", set())
        for x in range(px - 8, px + 9):
            for y in range(py - 8, py + 9):
                meta.add((x, y))
        # dropped loot, a fire pool, an in-flight arrow, and a target lock
        eng.world.ground_items[(px + 1, py)] = [create_item("sword")]
        eng.surfaces_layer.surfaces[(px - 1, py)] = {"kind": "fire"}
        eng.projectile_manager.active.append(
            types.SimpleNamespace(x=px + 0.5, y=py - 1.0, kind="arrow"))
        locked = None
        for npc in eng.npc_manager.npcs.values():
            if npc.is_active():
                eng.player_target_id = npc.id
                npc.position = (px, py + 1)          # keep it in view
                locked = npc
                break
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        try:
            iso_render.render_iso(surf, eng, pygame.Rect(0, 0, 640, 480), 48)
            # the gold reticle should have painted somewhere
            gold = any(
                abs(surf.get_at((x, y))[0] - 235) < 25 and
                abs(surf.get_at((x, y))[1] - 195) < 25 and
                surf.get_at((x, y))[2] < 110
                for x in range(0, 640, 3) for y in range(0, 480, 3))
            self.assertTrue(gold, "the ranged reticle should draw in iso")
        finally:
            eng.world.ground_items.pop((px + 1, py), None)
            eng.surfaces_layer.surfaces.pop((px - 1, py), None)
            eng.projectile_manager.active.clear()
            eng.player_target_id = None


class TestCombatEffectsExpire(unittest.TestCase):
    """Bug-fix: the iso path never AGED combat effects, so the red damage sprays
    stayed on screen forever (George)."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_iso_draw_ages_and_clears_the_sprays(self):
        from ui.iso import IsoProjection
        eng = self.engine
        ce = eng.combat_effects
        ce.damage_popups.clear()
        ce.death_effects.clear()
        px, py = eng.player.position
        ce.spawn_damage_popup(px, py, 12, (255, 60, 60))     # a red spray
        self.assertGreater(len(ce.damage_popups), 0, "spray spawned")
        iso = IsoProjection(48, 24, 12)
        surf = pygame.Surface((320, 240))
        view = pygame.Rect(0, 0, 320, 240)
        for _ in range(45):        # a DamagePopup lives ~1s = 30 frames at 1/30
            iso_render.draw_combat_iso(surf, eng, view, iso, (160, 120),
                                       eng.world.map, 48)
        self.assertEqual(len(ce.damage_popups), 0,
                         "the iso draw must age the spray away")


class TestBuildingFootprints(unittest.TestCase):
    """ISO.15 — buildings drawn as footprint-spanning boxes on the ground."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_footprint_tiles_cover_the_rect(self):
        from ui import iso_structures

        class _Loc:
            name, x, y, width, height = "House", 5, 6, 3, 2

        class _Eng:
            interiors = {"House": object()}
            world = type("W", (), {"locations": [_Loc()]})()
        tiles = iso_structures.footprint_tiles(_Eng())
        self.assertEqual(len(tiles), 6, "3x2 footprint = 6 tiles")
        self.assertIn((5, 6), tiles)
        self.assertIn((7, 7), tiles)

    def test_furrows_paint_green_crop_rows(self):
        # ISO.16: farmland reads as furrowed crops (green/gold rows)
        from ui import iso_tiles
        from ui.iso import IsoProjection
        iso = IsoProjection(80, 40, 20)
        surf = pygame.Surface((160, 120))
        surf.fill((124, 92, 56))                     # the dirt base
        iso_tiles.draw_furrows(surf, iso, 80, 60, 3, 4)
        greenish = sum(1 for x in range(30, 130, 3) for y in range(30, 90, 3)
                       if surf.get_at((x, y))[1] > surf.get_at((x, y))[0] + 10)
        self.assertGreater(greenish, 8, "crop rows should add green over dirt")

    def test_draw_building_paints_walls_and_roof(self):
        from ui import iso_structures
        from ui.iso import IsoProjection
        iso = IsoProjection(48, 24, 14)
        surf = pygame.Surface((300, 300))
        surf.fill((0, 0, 0))
        iso_structures.draw_building(surf, iso, (150, 90),
                                     (0, 0, 2, 2, "home"), "clay", "timber")
        painted = sum(1 for x in range(0, 300, 4) for y in range(0, 300, 4)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 30, "a spanning building should paint")


class TestIsoOverlayHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_draw_surface_paints_a_pool(self):
        from ui.iso import IsoProjection
        iso = IsoProjection(64, 32, 16)
        surf = pygame.Surface((128, 128))
        surf.fill((0, 0, 0))
        iso_render._draw_surface(surf, iso, ("fire", 64, 64, 0.0))
        painted = sum(1 for x in range(30, 98, 2) for y in range(48, 80, 2)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 10, "a fire pool should tint the tile")

    def test_draw_grounditem_blits(self):
        spr = pygame.Surface((32, 32))
        spr.fill((200, 80, 80))
        surf = pygame.Surface((128, 128))
        surf.fill((0, 0, 0))
        iso_render._draw_grounditem(surf, (spr, 64, 64))
        painted = sum(1 for x in range(40, 90, 2) for y in range(30, 80, 2)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 10, "dropped loot should blit on its tile")

    def test_get_sprites_is_cached(self):
        a = iso_render._get_sprites(48)
        b = iso_render._get_sprites(48)
        self.assertIs(a, b)

    def test_draw_pet_iso_paints(self):        # P41.12
        surf = pygame.Surface((128, 128))
        surf.fill((0, 0, 0))
        iso_render._draw_pet_iso(surf, ({"color": (210, 130, 60)}, 64, 64), 48)
        painted = sum(1 for x in range(40, 90, 2) for y in range(40, 96, 2)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 0, "the iso pet critter should draw")


class TestIsoCombatEffects(unittest.TestCase):        # P41.12
    @classmethod
    def setUpClass(cls):
        pygame.init()
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_draw_combat_iso_paints_a_death_burst(self):
        eng = self.engine
        px, py = eng.player.position
        eng.combat_effects.spawn_death_effect(px, py)
        eng.combat_effects.update(0.05)
        view = pygame.Rect(0, 0, 640, 480)
        iso = iso_render._projection(48)
        origin = iso_render._origin(iso, eng, view)
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        try:
            iso_render.draw_combat_iso(surf, eng, view, iso, origin,
                                       eng.world.map, 48)
            painted = sum(1 for x in range(0, 640, 4) for y in range(0, 480, 4)
                          if surf.get_at((x, y))[:3] != (0, 0, 0))
            self.assertGreater(painted, 0,
                               "combat effects should paint in the iso view")
        finally:
            eng.combat_effects.death_effects.clear()


if __name__ == "__main__":
    unittest.main()
