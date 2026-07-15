"""P39.6b — deterministic overworld decorative scatter (placement + sprites)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json
import unittest

import pygame

from ui import overworld_scatter as osc
from ui.scatter_sprites import scatter_sprite


class TestPlacement(unittest.TestCase):
    def test_is_deterministic(self):
        for wx, wy in ((3, 7), (40, 2), (128, 96)):
            self.assertEqual(osc.prop_at(wx, wy, "forest"),
                             osc.prop_at(wx, wy, "forest"))

    def test_sparse_density_matches_config(self):
        placed = tot = 0
        for wx in range(120):
            for wy in range(120):
                tot += 1
                if osc.prop_at(wx, wy, "grass") is not None:
                    placed += 1
        density = osc._data().get("density", 0.0)
        self.assertAlmostEqual(placed / tot, density, delta=0.03)

    def test_ineligible_terrain_scatters_nothing(self):
        for terrain in ("water", "road", "building", "mountain", "farmland"):
            hits = sum(1 for wx in range(60) for wy in range(60)
                       if osc.prop_at(wx, wy, terrain) is not None)
            self.assertEqual(hits, 0, f"{terrain} should carry no scatter")

    def test_only_recipe_props_appear(self):
        recipe = osc._data()["terrain"]["forest"]
        allowed = {e["prop"] for e in recipe} | {None}
        seen = {osc.prop_at(wx, wy, "forest")
                for wx in range(80) for wy in range(80)}
        self.assertTrue(seen <= allowed, f"unexpected props: {seen - allowed}")


class TestSprites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_every_recipe_prop_is_drawable(self):
        # guards against a JSON prop name with no sprite (would render nothing)
        data = osc._data()
        for terrain, recipe in data.get("terrain", {}).items():
            for entry in recipe:
                prop = entry["prop"]
                spr = scatter_sprite(prop, 48)
                self.assertIsNotNone(
                    spr, f"{terrain} prop '{prop}' has no sprite")
                painted = sum(1 for x in range(0, 48, 3)
                              for y in range(0, 48, 3)
                              if spr.get_at((x, y))[3] > 0)
                self.assertGreater(painted, 3,
                                   f"'{prop}' sprite is blank")

    def test_unknown_name_returns_none(self):
        self.assertIsNone(scatter_sprite("definitely_not_a_prop", 48))

    def test_sprites_are_cached(self):
        self.assertIs(scatter_sprite("boulder", 40),
                      scatter_sprite("boulder", 40))

    def test_scatter_is_grounded_with_a_shadow(self):
        # P40.3: a scatter piece has soft dark shadow pixels below its base
        # (it no longer floats). Boulder sits low-centre.
        spr = scatter_sprite("boulder", 48)
        shadow_band = [spr.get_at((x, y)) for x in range(16, 32)
                       for y in range(40, 46)]
        dark = [p for p in shadow_band if p[3] > 0 and sum(p[:3]) < 210]
        self.assertTrue(dark, "boulder should cast a grounding shadow")


class TestTopDownDraw(unittest.TestCase):
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

    def test_draw_scatter_paints_a_prop(self):
        from ui.scatter_draw import draw_scatter
        from ui.renderer import _TERRAIN_TO_SPRITE
        eng = self.engine
        px, py = eng.player.position
        wmap = eng.world.map
        meta = eng.player.metadata.setdefault("explored", set())
        # reveal + find a tile the scatter actually places a prop on
        spot = None
        for wy in range(max(0, py - 12), min(wmap.height, py + 13)):
            for wx in range(max(0, px - 12), min(wmap.width, px + 13)):
                meta.add((wx, wy))
                nm = _TERRAIN_TO_SPRITE.get(wmap.terrain[wy][wx], "grass")
                if spot is None and osc.prop_at(wx, wy, nm):
                    spot = (wx, wy)
        self.assertIsNotNone(spot, "the start area should carry some scatter")
        ts = 40
        cam_x, cam_y = spot[0] - 5, spot[1] - 5
        surf = pygame.Surface((11 * ts, 11 * ts), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        draw_scatter(surf, eng, pygame.Rect(0, 0, 11 * ts, 11 * ts),
                     cam_x, cam_y, ts)
        painted = sum(1 for x in range(0, 11 * ts, 4)
                      for y in range(0, 11 * ts, 4)
                      if surf.get_at((x, y))[3] > 0)
        self.assertGreater(painted, 0, "scatter should blit onto the view")


class TestJson(unittest.TestCase):
    def test_data_file_parses(self):
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "overworld_scatter.json")
        with open(p) as f:
            data = json.load(f)
        self.assertIn("terrain", data)
        self.assertGreater(data.get("density", 0), 0)


if __name__ == "__main__":
    unittest.main()
