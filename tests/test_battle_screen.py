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
from ui.battle_camera import (BattleCamera, CATEGORY_SHAPE,
                              LOD_BLOB_BELOW, TILE_SIZES,
                              category_shape, marker_points)


def _soldier_count(field):
    return sum(sq.strength for sq in field.squads.values())


class TestScenarios(unittest.TestCase):
    def test_there_are_scenarios(self):
        self.assertTrue(SCENARIOS)
        self.assertEqual(len(list_scenarios()), len(SCENARIOS))

    def test_a_broad_library(self):
        """The testbed spans many kinds of battle (P17.11 round)."""
        self.assertGreaterEqual(len(SCENARIOS), 20)
        # a spread of tactical set-pieces exists
        for sid in ("flanking_maneuver", "pike_wall", "last_stand",
                    "cavalry_charge", "gate_assault", "the_sortie",
                    "combined_arms", "river_ford", "hold_the_pass"):
            self.assertIn(sid, SCENARIOS)

    def test_terrain_and_unit_variety(self):
        """Across the library, many terrains and unit types appear."""
        terrains, units = set(), set()
        for sc in SCENARIOS.values():
            for patch in sc.get("terrain", []):
                terrains.add(patch["kind"])
            for army in sc.get("armies", []):
                for sq in army.get("squads", []):
                    units.add(sq["type"])
        # walls/water/forest/rubble/mountain cover the battlefield kinds
        self.assertTrue({"forest", "water", "rubble", "mountain"}
                        <= terrains, terrains)
        # infantry, cavalry, archers, siege all feature
        for u in ("infantry_sword", "infantry_pike", "cavalry_heavy",
                  "archer_longbow", "siege_ram", "siege_trebuchet"):
            self.assertIn(u, units)

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
            # big fields are watched interactively, not raced in the
            # suite — cap their tick budget so tests stay fast
            cap = 25 if _soldier_count(bf) > 60 else 400
            r = BattleSession(bf, seed=2).run_headless(max_ticks=cap)
            # either someone wins or it ran the clock — never crashes
            self.assertIn("winner", r)
            self.assertLessEqual(r["ticks"], cap)

    def test_a_large_battle_scales(self):
        """Hundreds of soldiers on a wide field tick without error."""
        bf = build_field("grand_clash")
        self.assertGreater(_soldier_count(bf), 200)
        self.assertGreaterEqual(bf.width, 100)
        sess = BattleSession(bf, seed=1)
        for _ in range(10):
            sess.tick()
        self.assertEqual(sess.tick_count, 10)

    def test_ranged_squads_emit_tracers(self):
        """A bow squad in range of a foe records a shot to draw."""
        bf = build_field("storm_the_breach")
        sess = BattleSession(bf, seed=1)
        saw_tracer = False
        for _ in range(120):
            if sess.over():
                break
            sess.tick()
            if sess.tracers:
                # a tracer is (x0, y0, x1, y1) within the field
                for (x0, y0, x1, y1) in sess.tracers:
                    self.assertTrue(bf.in_bounds(x0, y0))
                    self.assertTrue(bf.in_bounds(x1, y1))
                saw_tracer = True
                break
        self.assertTrue(saw_tracer, "archers never fired a visible shot")

    def test_tracers_reset_each_tick(self):
        bf = build_field("open_field")   # pure melee — never any shots
        sess = BattleSession(bf, seed=1)
        for _ in range(8):
            sess.tick()
            self.assertEqual(sess.tracers, [], "melee makes no tracers")


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


class TestUnitIcons(unittest.TestCase):
    def test_each_category_has_a_shape(self):
        for cat in ("infantry", "cavalry", "archer", "siege",
                    "beast", "support"):
            self.assertIn(cat, CATEGORY_SHAPE)
        self.assertEqual(category_shape("nonsense"), "circle")

    def test_the_melee_types_are_visually_distinct(self):
        shapes = {category_shape(c) for c in
                  ("infantry", "cavalry", "archer", "siege")}
        self.assertEqual(len(shapes), 4, "each reads as its own glyph")

    def test_polygon_markers_have_enough_vertices(self):
        for shape in ("triangle", "diamond", "square", "hex"):
            pts = marker_points(shape, 100, 100, 8)
            self.assertGreaterEqual(len(pts), 3)
            for (x, y) in pts:      # all within the marker's box
                self.assertLessEqual(abs(x - 100), 8.01)
                self.assertLessEqual(abs(y - 100), 8.01)

    def test_circle_and_cross_are_not_polygons(self):
        self.assertEqual(marker_points("circle", 0, 0, 5), [])
        self.assertEqual(marker_points("cross", 0, 0, 5), [])

    def test_scenario_unit_types_all_map_to_a_shape(self):
        for sid in SCENARIOS:
            for sq in build_field(sid).squads.values():
                self.assertIn(category_shape(sq.category),
                              ("circle", "triangle", "diamond",
                               "square", "hex", "cross"))


if __name__ == "__main__":
    unittest.main()
