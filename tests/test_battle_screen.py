"""Battle testbed (P17.4): scenario building + the camera math.

The pygame drawing in ui/battle_screen.py is render-only and not
unit-tested; the load-bearing logic — that scenarios expand into
tickable fields and the camera's zoom/LOD/transform arithmetic is
correct — is tested here headless.
"""

import unittest

from engine.battle import BattleSession
from engine.battle.battle_scenario import (SCENARIOS, build_field,
                                           list_scenarios,
                                           team_strengths)
from ui.battle_camera import (BattleCamera, LOD_BLOB_BELOW,
                              TILE_SIZES)


class TestScenarios(unittest.TestCase):
    def test_there_are_scenarios(self):
        self.assertTrue(SCENARIOS)
        self.assertEqual(len(list_scenarios()), len(SCENARIOS))

    def test_every_scenario_builds_two_sided(self):
        for sid in SCENARIOS:
            bf = build_field(sid)
            strengths = team_strengths(bf)
            self.assertGreaterEqual(len(strengths), 2,
                                    f"{sid} needs two sides")
            for team, n in strengths.items():
                self.assertGreater(n, 0, f"{sid}/{team} empty")

    def test_soldiers_are_placed_in_bounds_and_unique(self):
        for sid in SCENARIOS:
            bf = build_field(sid)
            seen = set()
            for sq in bf.squads.values():
                for s in sq.alive_soldiers:
                    self.assertTrue(bf.in_bounds(s.x, s.y),
                                    f"{sid}: {s.sid} off-field")
                    self.assertNotIn((s.x, s.y), seen,
                                     f"{sid}: overlap at {s.pos}")
                    seen.add((s.x, s.y))

    def test_unknown_scenario_raises(self):
        with self.assertRaises(KeyError):
            build_field("no_such_scenario")

    def test_every_scenario_converges_headless(self):
        for sid in SCENARIOS:
            bf = build_field(sid)
            r = BattleSession(bf, seed=2).run_headless(max_ticks=400)
            # either someone wins or it ran the full clock — never crashes
            self.assertIn("winner", r)
            self.assertLessEqual(r["ticks"], 400)


class TestCamera(unittest.TestCase):
    def _cam(self):
        return BattleCamera(40, 26, 800, 600, tile_size=32)

    def test_zoom_steps_through_allowed_sizes(self):
        cam = self._cam()
        cam.tile_size = TILE_SIZES[0]
        seen = [cam.tile_size]
        for _ in range(6):
            cam.zoom_in()
            seen.append(cam.tile_size)
        self.assertEqual(seen[-1], TILE_SIZES[-1], "clamps at max")
        for ts in seen:
            self.assertIn(ts, TILE_SIZES)

    def test_zoom_out_clamps_at_min(self):
        cam = self._cam()
        for _ in range(6):
            cam.zoom_out()
        self.assertEqual(cam.tile_size, TILE_SIZES[0])

    def test_blob_mode_only_below_threshold(self):
        cam = self._cam()
        cam.tile_size = 8
        self.assertTrue(cam.blob_mode)
        cam.tile_size = 16
        self.assertFalse(cam.blob_mode)
        cam.tile_size = 32
        self.assertFalse(cam.blob_mode)
        self.assertLess(8, LOD_BLOB_BELOW)

    def test_world_screen_round_trip(self):
        cam = self._cam()
        for wx, wy in ((0, 0), (10, 5), (39, 25), (20.5, 13.5)):
            sx, sy = cam.world_to_screen(wx, wy)
            bx, by = cam.screen_to_world(sx, sy)
            self.assertAlmostEqual(wx, bx, places=4)
            self.assertAlmostEqual(wy, by, places=4)

    def test_camera_center_maps_to_screen_center(self):
        cam = self._cam()
        sx, sy = cam.world_to_screen(cam.cx, cam.cy)
        self.assertAlmostEqual(sx, cam.vw / 2)
        self.assertAlmostEqual(sy, cam.vh / 2)

    def test_visible_bounds_within_field(self):
        cam = self._cam()
        for ts in TILE_SIZES:
            cam.tile_size = ts
            x0, y0, x1, y1 = cam.visible_tile_bounds()
            self.assertGreaterEqual(x0, 0)
            self.assertGreaterEqual(y0, 0)
            self.assertLessEqual(x1, cam.fw - 1)
            self.assertLessEqual(y1, cam.fh - 1)
            self.assertLessEqual(x0, x1)
            self.assertLessEqual(y0, y1)

    def test_pan_clamps_to_field(self):
        cam = self._cam()
        cam.pan(-1000, -1000)
        self.assertEqual((cam.cx, cam.cy), (0.0, 0.0))
        cam.pan(1000, 1000)
        self.assertEqual((cam.cx, cam.cy), (float(cam.fw), float(cam.fh)))


if __name__ == "__main__":
    unittest.main()
