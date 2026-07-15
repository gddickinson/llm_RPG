"""P39.4 — interior light sources & mood (warm glow, darkness, dust)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from ui import interior_light as il


class _Zone:
    def __init__(self, w, h, furniture):
        self.width, self.height = w, h
        self.furniture = furniture


def _brightness(surf, rect):
    x, y, w, h = rect
    tot = 0
    n = 0
    for px in range(x, x + w, 4):
        for py in range(y, y + h, 4):
            c = surf.get_at((px, py))
            tot += c[0] + c[1] + c[2]
            n += 1
    return tot / max(1, n)


class TestSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_hole_and_glow_cache(self):
        self.assertIs(il._hole(30), il._hole(30))
        self.assertIs(il._glow(20, (255, 170, 70)), il._glow(20, (255, 170, 70)))

    def test_glow_is_bright_at_centre_dark_at_edge(self):
        g = il._glow(24, (255, 170, 70))
        centre = sum(g.get_at((24, 24))[:3])
        edge = sum(g.get_at((1, 24))[:3])
        self.assertGreater(centre, edge)


class TestDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def _target(self):
        s = pygame.Surface((320, 320))
        s.fill((80, 80, 80))                 # mid-grey room
        return s

    def test_a_brazier_lights_its_surroundings_warmer(self):
        ts = 32
        zone = _Zone(10, 10, [{"name": "Brazier", "x": 5, "y": 5}])
        theme = {"light": {"dark": 120, "glow": [255, 150, 60]}}
        target = self._target()
        view = pygame.Rect(0, 0, 320, 320)
        il.draw(target, zone, view, 0, 0, ts, theme, player_pos=None)
        near = _brightness(target, (5 * ts - 8, 5 * ts - 8, 16, 16))
        far = _brightness(target, (0, 0, 16, 16))
        self.assertGreater(near, far, "the brazier should light its area")

    def test_dark_theme_darkens_the_room(self):
        ts = 32
        zone = _Zone(10, 10, [])            # no lights
        view = pygame.Rect(0, 0, 320, 320)
        dark = self._target()
        il.draw(dark, zone, view, 0, 0, ts,
                {"light": {"dark": 130, "glow": [255, 150, 60]}})
        lit = self._target()
        il.draw(lit, zone, view, 0, 0, ts,
                {"light": {"dark": 0, "glow": [255, 150, 60]}})
        self.assertLess(_brightness(dark, (100, 100, 40, 40)),
                        _brightness(lit, (100, 100, 40, 40)))

    def test_no_light_key_is_a_safe_noop(self):
        target = self._target()
        before = _brightness(target, (0, 0, 320, 320))
        il.draw(target, _Zone(10, 10, []), pygame.Rect(0, 0, 320, 320),
                0, 0, 32, {})
        self.assertEqual(_brightness(target, (0, 0, 320, 320)), before)


class TestIsoLight(unittest.TestCase):
    """P41.9 — the same mood over the isometric projection."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def _target(self):
        s = pygame.Surface((320, 320))
        s.fill((80, 80, 80))
        return s

    def _iso_origin(self, iso, fx, fy):
        # centre the lit tile in the 320×320 view
        sx, sy = iso.world_to_screen(fx, fy, 0)
        return (160 - sx, 160 - sy)

    def test_brazier_lights_its_iso_surroundings(self):
        from ui.iso import IsoProjection
        iso = IsoProjection(32, 16, 12)
        zone = _Zone(10, 10, [{"name": "Brazier", "x": 5, "y": 5}])
        theme = {"light": {"dark": 120, "glow": [255, 150, 60]}}
        origin = self._iso_origin(iso, 5, 5)
        target = self._target()
        view = pygame.Rect(0, 0, 320, 320)
        il.draw_iso(target, zone, view, iso, origin, 32, theme,
                    player_pos=None)
        near = _brightness(target, (152, 152, 16, 16))   # the tile centre
        far = _brightness(target, (0, 0, 16, 16))
        self.assertGreater(near, far, "the iso brazier should light its area")

    def test_seen_gates_a_lit_prop_on_dark_levels(self):
        from ui.iso import IsoProjection
        iso = IsoProjection(32, 16, 12)
        zone = _Zone(10, 10, [{"name": "Brazier", "x": 5, "y": 5}])
        theme = {"light": {"dark": 120, "glow": [255, 150, 60]}}
        origin = self._iso_origin(iso, 5, 5)
        view = pygame.Rect(0, 0, 320, 320)
        # brazier NOT in the seen set → no warm pool at its tile
        target = self._target()
        il.draw_iso(target, zone, view, iso, origin, 32, theme,
                    player_pos=None, seen={(1, 1)})
        near = _brightness(target, (152, 152, 16, 16))
        # with it seen → the pool returns
        target2 = self._target()
        il.draw_iso(target2, zone, view, iso, origin, 32, theme,
                    player_pos=None, seen={(5, 5)})
        near2 = _brightness(target2, (152, 152, 16, 16))
        self.assertGreater(near2, near, "an unseen prop should stay unlit")

    def test_draw_screen_shared_core(self):
        theme = {"light": {"dark": 120, "glow": [255, 150, 60]}}
        target = self._target()
        view = pygame.Rect(0, 0, 320, 320)
        il.draw_screen(target, view, 32, theme, [(160, 160)],
                       player_screen=None)
        near = _brightness(target, (152, 152, 16, 16))
        far = _brightness(target, (0, 0, 16, 16))
        self.assertGreater(near, far)


if __name__ == "__main__":
    unittest.main()
