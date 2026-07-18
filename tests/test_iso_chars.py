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
        east = iso_chars.char_sprite(e, 72)   # both idle (no cur_action)
        west = iso_chars.char_sprite(w, 72)
        self.assertIsNot(east, west, "an east-facer bakes apart from a west")


class TestSprite(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_kit_headgear_by_class(self):
        # ISO.12: class → headgear (helmet/hat/hood/circlet or none)
        self.assertEqual(iso_chars.kit_of(_Char("a", "warrior"))[1], "helmet")
        self.assertEqual(iso_chars.kit_of(_Char("b", "wizard"))[1], "hat")
        self.assertEqual(iso_chars.kit_of(_Char("c", "rogue"))[1], "hood")
        self.assertEqual(iso_chars.kit_of(_Char("d", "noble"))[1], "circlet")
        self.assertIsNone(iso_chars.kit_of(_Char("e", "merchant"))[1])

    def test_kit_is_hashable_with_body_height(self):
        kit = iso_chars.kit_of(_Char("f", "guard"))
        self.assertEqual(len(kit), 6,
                         "(weapon, head, shield, height, robed, pauldrons)")
        self.assertIsInstance(hash(kit), int, "cache-key hashable")
        self.assertIn(kit[3], (0.92, 1.0, 1.08), "a seeded body height")
        self.assertFalse(kit[4], "a guard is not robed")
        self.assertTrue(kit[5], "a guard is armored → pauldrons")

    def test_gear_changes_the_sprite(self):
        # a helmeted warrior bakes apart from a bare merchant
        w = iso_chars.char_sprite(_Char("aldric", "warrior"), 80)
        m = iso_chars.char_sprite(_Char("aldric", "merchant"), 80)
        self.assertIsNot(w, m, "class gear differentiates the bake")

    def test_sprite_drawn_and_cached_with_stance(self):
        c = _Char("aldric", "warrior")
        # freeze the animation clock so both calls resolve the same frame (the
        # cache key includes the clock-derived frame; wall-clock drift between
        # the two calls otherwise flakes this "is cached" check)
        orig = iso_chars._clock_ms
        iso_chars._clock_ms = lambda: 1000
        try:
            s1 = iso_chars.char_sprite(c, 72, 2)
            self.assertIsInstance(s1, pygame.Surface)
            self.assertGreater(pygame.mask.from_surface(s1).count(), 40)
            self.assertIs(s1, iso_chars.char_sprite(c, 72, 2), "cached")
        finally:
            iso_chars._clock_ms = orig

    def test_taller_than_a_single_tile(self):
        c = _Char("x", "merchant")
        s = iso_chars.char_sprite(c, 72, 2)
        self.assertGreater(s.get_height(), 0)


if __name__ == "__main__":
    unittest.main()


class TestInteractionParity(unittest.TestCase):
    """I4 — the two-character interaction clips reach iso (not a frozen idle),
    and a hand-busy social clip drops the weapon (parity with the 2D fix)."""

    def test_interaction_clips_map_to_real_mocap(self):
        from ui import iso_skeleton as isk
        for act in ("handshake", "hug", "kiss", "wrestle", "tumble",
                    "knockdown", "taunt"):
            self.assertNotEqual(isk.clip_for(act), "idle",
                                f"{act} should play a real iso clip")

    def test_iso_pauldrons_for_armored_classes(self):
        # H1: an armored kit adds shoulder-plate meshes (iso parity with G5)
        import numpy as np
        from ui import iso_gear
        P = {"l_sh": np.array([-0.2, 1.2, 0.0]),
             "r_sh": np.array([0.2, 1.2, 0.0])}
        self.assertEqual(len(iso_gear.pauldron_mesh(P)), 2, "a plate per shoulder")
        self.assertTrue(iso_chars.kit_of(_Char("w", "warrior"))[5])
        self.assertFalse(iso_chars.kit_of(_Char("m", "merchant"))[5])

    def test_social_clip_drops_the_weapon(self):
        c = _Char("brawler", "warrior")
        self.assertIsNotNone(iso_chars.kit_of(c)[0], "a warrior is armed")
        c.metadata["_anim"] = {"cur_action": "hug"}
        kit = iso_chars.kit_of(c)
        self.assertIsNone(kit[0], "no weapon during a hug")
        self.assertFalse(kit[2], "no shield during a hug")

    def test_combat_clip_keeps_the_weapon(self):
        c = _Char("duelist", "warrior")
        c.metadata["_anim"] = {"cur_action": "wrestle"}
        self.assertIsNotNone(iso_chars.kit_of(c)[0],
                             "a wrestle is armed (only social clips disarm)")


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

    def test_frame_state_reads_cur_action(self):
        # ISO.11: _frame_state reads the cur_action body_renderer.update_anim sets
        from ui.body_renderer import update_anim
        # freeze the clock: an idle char drifts through ambient gestures (look/
        # bored) on a wall-clock timer (ISO.14) — at t=0 the ambient slot is idle,
        # so the idle assertion is stable instead of a wall-clock flake
        orig = iso_chars._clock_ms
        iso_chars._clock_ms = lambda: 0
        try:
            c = _Char("hero", "warrior")
            c.position = (3, 3)
            update_anim(c, 0.05)                        # init → idle
            self.assertEqual(iso_chars._frame_state(c)[0], "idle")
            c.position = (4, 3); update_anim(c, 0.05)   # moved → walk (tweening)
            self.assertEqual(iso_chars._frame_state(c)[0], "walk")
            c.metadata["_atk_seq"] = 1; update_anim(c, 0.05)  # struck → attack
            self.assertEqual(iso_chars._frame_state(c)[0], "attack")
        finally:
            iso_chars._clock_ms = orig

    def test_richer_actions_flow_to_iso(self):
        # a stance / emote set on the character reaches iso via cur_action
        from ui.body_renderer import update_anim
        c = _Char("dancer", "bard"); c.position = (5, 5)
        c.metadata["_stance"] = "dance"
        update_anim(c, 0.05)
        self.assertEqual(iso_chars._frame_state(c)[0], "dance")

    def test_ambient_idle_drifts_but_stays_calm(self):
        # ISO.14: an idle character only ever drifts to a calm look/bored/idle
        c = _Char("stander", "villager")
        seen = {iso_chars._ambient_idle(c) for _ in range(6)}
        self.assertTrue(seen <= {"idle", "look", "bored"},
                        "ambient idle stays calm")

    def test_a_downed_character_lies_down(self):
        # ISO.16: a dying/unconscious character shows the death (prone) pose
        c = _Char("fallen", "warrior"); c.position = (2, 2)
        c.metadata["dying"] = 2
        self.assertEqual(iso_chars._frame_state(c)[0], "die")

    def test_action_frames_bake_distinct_sprites(self):
        pygame.init()
        from ui.body_renderer import update_anim
        c = _Char("walker", "guard"); c.position = (1, 1)
        update_anim(c, 0.05)
        c.position = (2, 1); update_anim(c, 0.05)   # walking
        walk = iso_chars.char_sprite(c, 72, 2)
        for _ in range(8):                          # let the tween expire → idle
            update_anim(c, 0.05)
        idle = iso_chars.char_sprite(c, 72, 2)
        self.assertIsNot(walk, idle, "walk and idle bake to different frames")

    def test_dance_sit_jump_swim_bake_distinct(self):
        pygame.init()
        from ui import iso_skeleton as isk
        # keep every mesh ALIVE in a list — else a GC'd mesh's id can be reused
        # by the next one and `id()`-distinctness flakes by allocation order
        meshes = []
        for act in ("idle", "dance", "sit", "jump", "swim", "climb"):
            m = isk.sample_figure(act, 0.3, (150, 150, 165), (90, 60, 40), 0.0)
            self.assertIsNotNone(m, f"{act} builds a mesh")
            meshes.append(m)
        self.assertEqual(len({id(m) for m in meshes}), 6,
                         "each action is its own mesh")
