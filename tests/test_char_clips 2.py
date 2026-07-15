"""P33.6b — the animation clip library + the action state machine."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_cc_"))

import unittest

from ui import char_clips as cc
from ui import char_pose as cp


def _base(**kw):
    return cp.build_pose(100, 200, 60, **kw)


class TestRegistry(unittest.TestCase):
    def test_one_shot_vs_loop(self):
        self.assertTrue(cc.is_one_shot("jump"))
        self.assertFalse(cc.is_one_shot("idle"))
        self.assertTrue(cc.is_one_shot("bow"))
        self.assertIsNotNone(cc.duration("bow"))
        self.assertIsNone(cc.duration("sit"))

    def test_unknown_action_is_a_noop(self):
        base = _base()
        self.assertEqual(cc.apply("no_such", base, 0.5, 60, (0, 1)), base)
        self.assertEqual(cc.apply("idle", base, 0.5, 60, (0, 1)), base)


class TestClips(unittest.TestCase):
    def _apply(self, action, phase=0.5, facing=(0, 1)):
        return cc.apply(action, _base(facing=facing), phase, 60, facing)

    def test_jump_lifts_the_whole_body(self):
        rest = _base()
        j = self._apply("jump", 0.5)
        self.assertLess(j["head"][1], rest["head"][1])         # head higher
        self.assertLess(j["l_foot"][1], rest["l_foot"][1])     # feet off ground

    def test_sit_lowers_the_body(self):
        rest = _base()
        s = self._apply("sit")
        self.assertGreater(s["chest"][1], rest["chest"][1])    # torso drops

    def test_bow_bends_the_upper_body_down(self):
        rest = _base()
        b = self._apply("bow", 0.5)
        self.assertGreater(b["head"][1], rest["head"][1])      # head dips

    def test_wave_raises_the_right_hand(self):
        rest = _base()
        w = self._apply("wave", 0.3)
        self.assertLess(w["r_hand"][1], rest["r_hand"][1])

    def test_cheer_raises_both_hands(self):
        rest = _base()
        c = self._apply("cheer", 0.5)
        self.assertLess(c["l_hand"][1], rest["l_hand"][1])
        self.assertLess(c["r_hand"][1], rest["r_hand"][1])

    def test_clips_do_not_mutate_the_base(self):
        base = _base()
        snapshot = dict(base)
        cc.apply("jump", base, 0.5, 60, (0, 1))
        self.assertEqual(base["head"], snapshot["head"])       # worked on a copy

    def test_swim_submerges(self):
        rest = _base()
        s = self._apply("swim", 0.3)
        self.assertGreater(s["chest"][1], rest["chest"][1])    # body sinks

    def test_climb_raises_both_hands(self):
        rest = _base()
        c = self._apply("climb", 0.4)
        self.assertLess(c["l_hand"][1], rest["l_hand"][1])
        self.assertLess(c["r_hand"][1], rest["r_hand"][1])

    def test_kneel_lowers_and_bows(self):
        rest = _base()
        k = self._apply("kneel")
        self.assertGreater(k["head"][1], rest["head"][1])      # lower + bowed

    def test_reach_extends_the_hand_forward(self):
        rest = _base()                             # front: hand rests at the side
        r = cc.apply("reach", _base(), 0.9, 60, (0, 1))
        self.assertGreater(r["r_hand"][0], rest["r_hand"][0])  # hand reaches out

    def test_handshake_extends_the_hand(self):
        rest = _base()
        h = self._apply("handshake", 0.5)
        self.assertGreater(h["r_hand"][0], rest["r_hand"][0])

    def test_hug_brings_both_hands_forward(self):
        rest = _base()
        hg = self._apply("hug", 0.6)
        self.assertGreater(hg["l_hand"][0], rest["l_hand"][0])
        self.assertGreater(hg["r_hand"][0], rest["r_hand"][0])

    def test_knockdown_falls_then_rises(self):
        rest = _base()
        down = self._apply("knockdown", 0.5)       # lying
        up = self._apply("knockdown", 0.98)        # back on the feet
        self.assertGreater(down["head"][1], rest["head"][1])   # head near ground
        self.assertLess(up["head"][1], down["head"][1])        # risen again


class _Char:
    def __init__(self):
        self.metadata = {}
        self.position = (5, 5)


class TestActionStateMachine(unittest.TestCase):
    def setUp(self):
        from ui.body_renderer import update_anim, _ensure_anim
        self.update = update_anim
        self.ensure = _ensure_anim
        self.c = _Char()
        self.update(self.c, 1 / 30)      # prime

    def _anim(self):
        return self.c.metadata["_anim"]

    def test_idle_by_default(self):
        self.update(self.c, 1 / 30)
        self.assertEqual(self._anim()["cur_action"], "idle")

    def test_emote_plays_then_reverts(self):
        self.c.metadata["_emote"] = "bow"
        self.update(self.c, 1 / 30)
        self.assertEqual(self._anim()["cur_action"], "bow")
        self.assertGreater(self._anim()["action_t"], 0)
        # run the clock past the duration → back to idle
        for _ in range(60):
            self.update(self.c, 1 / 30)
        self.assertEqual(self._anim()["cur_action"], "idle")

    def test_stance_holds(self):
        self.c.metadata["_stance"] = "guard"
        self.update(self.c, 1 / 30)
        self.assertEqual(self._anim()["cur_action"], "guard")

    def test_moving_walks(self):
        self.c.position = (6, 5)         # stepped
        self.update(self.c, 1 / 30)
        self.assertEqual(self._anim()["cur_action"], "walk")

    def test_hurt_cuts_in_over_a_playing_emote(self):
        self.c.metadata["_emote"] = "bow"
        self.update(self.c, 1 / 30)
        self.c.metadata["_emote"] = "hurt"
        self.update(self.c, 1 / 30)
        self.assertEqual(self._anim()["cur_action"], "hurt")

    def test_face_request_turns_the_character(self):
        self.c.metadata["_face"] = (-1, 0)
        self.update(self.c, 1 / 30)
        self.assertEqual(self._anim()["facing"], (-1, 0))


if __name__ == "__main__":
    unittest.main()
