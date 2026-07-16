"""ISO.3 — richer baked iso character figures (headless)."""

import unittest

import pygame

from ui import iso_chars


class _Char:
    def __init__(self, cid, cls, hair="hair_brown"):
        self.id = cid
        self.character_class = type("K", (), {"value": cls})()
        self.hair = hair
        self.metadata = {}


class TestFigure(unittest.TestCase):
    def test_figure_has_legs_torso_arms_head(self):
        parts = iso_chars._figure((150, 150, 165), (90, 60, 40), 2, stance=1)
        # 2 legs + waist + chest + 2 arms + head + hair + nose = 9 parts
        self.assertGreaterEqual(len(parts), 9, "arms + two legs now present")

    def test_stance_shifts_the_body(self):
        left = iso_chars._figure((150,) * 3, (90, 60, 40), 2, stance=0)
        right = iso_chars._figure((150,) * 3, (90, 60, 40), 2, stance=2)
        # the chest box (index 3) sits at a different x for opposite stances
        self.assertNotEqual(left[3][0].mean(axis=0)[0],
                            right[3][0].mean(axis=0)[0])

    def test_stance_is_stable_per_person(self):
        c = _Char("bess", "villager")
        self.assertEqual(iso_chars._stance_of(c), iso_chars._stance_of(c))
        self.assertIn(iso_chars._stance_of(c), (0, 1, 2))


class TestFacing(unittest.TestCase):
    """ISO.9 — the figure faces the iso-SCREEN direction it actually moves
    (the calibrated inverse of the camera's perspective foreshortening)."""

    def _char(self, dxdy):
        c = _Char("mover", "warrior")
        c.metadata = {"_anim": {"facing": dxdy}}
        return c

    def test_move_delta_reads_the_sign_tuple(self):
        self.assertEqual(iso_chars.move_delta(self._char((0, -1))), (0, -1))
        self.assertEqual(iso_chars.move_delta(self._char((3, 0))), (1, 0))
        self.assertEqual(iso_chars.move_delta(self._char((-2, 2))), (-1, 1))

    def test_still_faces_the_camera(self):
        self.assertEqual(iso_chars.move_delta(self._char((0, 0))), (0, 1))
        self.assertEqual(iso_chars.move_delta(_Char("x", "guard")), (0, 1))

    def test_angle_makes_the_figure_face_the_move(self):
        # for each grid move, the chosen rotation's forward must project to the
        # move's iso-screen direction (dx-dy, dx+dy) within a tight tolerance
        import math
        from ui import iso_skeleton as isk
        for dx, dy in iso_chars._DELTAS:
            a = isk.angle_for_delta(dx, dy)
            got = isk._fwd_screen_angle(a)
            want = math.atan2(dx + dy, dx - dy)
            diff = abs((got - want + math.pi) % (2 * math.pi) - math.pi)
            self.assertLess(math.degrees(diff), 12,
                            f"move ({dx},{dy}) should face its screen heading")

    def test_opposite_moves_face_opposite_ways(self):
        import math
        from ui import iso_skeleton as isk
        # east vs west: their forward screen directions point apart
        ae = isk._fwd_screen_angle(isk.angle_for_delta(1, 0))
        aw = isk._fwd_screen_angle(isk.angle_for_delta(-1, 0))
        spread = abs((ae - aw + math.pi) % (2 * math.pi) - math.pi)
        self.assertGreater(math.degrees(spread), 120, "E and W face apart")

    def test_different_facings_bake_different_sprites(self):
        pygame.init()
        e, w = self._char((1, 0)), self._char((-1, 0))
        for c in (e, w):
            c.metadata["_iso_walk_until"] = 0
            c.metadata["_iso_atk_until"] = 0
        east = iso_chars.char_sprite(e, 72)
        west = iso_chars.char_sprite(w, 72)
        self.assertIsNot(east, west, "an east-facer bakes apart from a west")


class TestSprite(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_sprite_drawn_and_cached_with_stance(self):
        c = _Char("aldric", "warrior")
        s1 = iso_chars.char_sprite(c, 72, 2)
        self.assertIsInstance(s1, pygame.Surface)
        self.assertGreater(pygame.mask.from_surface(s1).count(), 40)
        self.assertIs(s1, iso_chars.char_sprite(c, 72, 2), "cached")

    def test_taller_than_a_single_tile(self):
        c = _Char("x", "merchant")
        s = iso_chars.char_sprite(c, 72, 2)
        self.assertGreater(s.get_height(), 0)


if __name__ == "__main__":
    unittest.main()


class TestAnimation(unittest.TestCase):
    def test_walk_pose_moves_the_legs(self):
        rest = iso_chars._rest_parts((150,) * 3, (90, 60, 40), 1)
        idle = iso_chars._pose(rest, "idle", 0.0)
        walk = iso_chars._pose(rest, "walk", 0.25)   # mid-stride
        # the left leg (index 0) is displaced in the walk pose
        import numpy as np
        self.assertGreater(
            float(np.abs(np.asarray(walk[0][0]) - np.asarray(idle[0][0])).max()),
            0.05, "the leg strides")

    def test_walk_frames_differ(self):
        rest = iso_chars._rest_parts((150,) * 3, (90, 60, 40), 1)
        import numpy as np
        # the stride EXTREMES (leg forward vs back) — 0.0/0.5 both cross neutral
        a = np.asarray(iso_chars._pose(rest, "walk", 0.25)[0][0])
        b = np.asarray(iso_chars._pose(rest, "walk", 0.75)[0][0])
        self.assertGreater(float(np.abs(a - b).max()), 0.05,
                           "opposite stride phases differ")

    def test_attack_raises_the_weapon_arm(self):
        rest = iso_chars._rest_parts((150,) * 3, (90, 60, 40), 1)
        import numpy as np
        rest_arm = np.asarray(rest[5][0])[:, 1].max()
        atk_arm = np.asarray(
            iso_chars._pose(rest, "attack", 0.5)[5][0])[:, 1].max()
        self.assertGreater(atk_arm, rest_arm, "the arm arcs up in a strike")

    def test_frame_state_transitions(self):
        c = _Char("hero", "warrior")
        c.position = (3, 3)
        self.assertEqual(iso_chars._frame_state(c)[0], "idle")
        c.position = (4, 3)                         # moved
        self.assertEqual(iso_chars._frame_state(c)[0], "walk")
        c.metadata["_atk_seq"] = 1                  # struck
        self.assertEqual(iso_chars._frame_state(c)[0], "attack")

    def test_action_frames_bake_distinct_sprites(self):
        pygame.init()
        c = _Char("walker", "guard")
        c.position = (1, 1)
        iso_chars._frame_state(c)                   # prime pos
        c.position = (2, 1)
        walk = iso_chars.char_sprite(c, 72, 2)
        # force idle
        c.metadata["_iso_walk_until"] = 0
        c.metadata["_iso_atk_until"] = 0
        idle = iso_chars.char_sprite(c, 72, 2)
        self.assertIsNot(walk, idle, "walk and idle bake to different frames")
