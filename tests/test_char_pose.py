"""P33.4b — the pure character-pose skeleton math + a big-body render smoke."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_cp_"))

import math
import unittest

from ui import char_pose as cp


class TestPose(unittest.TestCase):
    def _pose(self, **kw):
        args = dict(cx=100, foot_y=200, H=60)
        args.update(kw)
        return cp.build_pose(**args)

    def test_has_all_joints(self):
        p = self._pose()
        for j in ("l_foot", "r_foot", "l_knee", "r_knee", "l_hip", "r_hip",
                  "l_sh", "r_sh", "l_hand", "r_hand", "head", "neck"):
            self.assertIn(j, p)
        self.assertGreater(p["head_r"], 0)

    def test_body_rises_from_the_feet(self):
        p = self._pose()
        self.assertAlmostEqual(p["l_foot"][1], 200, delta=1)   # feet at ground
        self.assertLess(p["head"][1], p["l_hip"][1])           # head above hips
        self.assertLess(p["l_hip"][1], p["l_foot"][1])         # hips above feet

    def test_walk_swings_the_feet(self):
        fwd = self._pose(walk=math.pi / 2, moving=True)        # sin > 0
        back = self._pose(walk=3 * math.pi / 2, moving=True)   # sin < 0
        # the left foot steps FORWARD (greater x) when sin(walk) > 0
        self.assertGreater(fwd["l_foot"][0], back["l_foot"][0])
        # …and the right foot does the opposite
        self.assertLess(fwd["r_foot"][0], back["r_foot"][0])

    def test_attack_raises_the_weapon_hand(self):
        rest = self._pose(attack=0.0)
        mid = self._pose(attack=0.5)
        self.assertLess(mid["r_hand"][1], rest["r_hand"][1])   # hand swings up

    def test_build_scales_head_and_shoulders(self):
        big = self._pose(build={"shoulder": 1.4, "hip": 1.0, "head": 1.5,
                                "girth": 1.5})
        small = self._pose(build={"shoulder": 0.8, "hip": 1.0, "head": 0.8,
                                  "girth": 0.8})
        self.assertGreater(big["head_r"], small["head_r"])
        big_shw = big["r_sh"][0] - big["l_sh"][0]
        small_shw = small["r_sh"][0] - small["l_sh"][0]
        self.assertGreater(big_shw, small_shw)
        self.assertEqual(big["girth"], 1.5)

    def test_weapon_dir_by_facing(self):
        self.assertEqual(cp.weapon_dir((1, 0)), 1)
        self.assertEqual(cp.weapon_dir((-1, 0)), -1)
        self.assertEqual(cp.weapon_dir((0, -1)), 0)            # facing away
        self.assertEqual(cp.weapon_dir((0, 1)), 1)            # facing camera


class TestSideProfile(unittest.TestCase):
    def _pose(self, facing):
        return cp.build_pose(100, 200, 60, facing=facing)

    def test_profile_flag(self):
        self.assertEqual(self._pose((1, 0))["profile"], 1)
        self.assertEqual(self._pose((-1, 0))["profile"], -1)
        self.assertEqual(self._pose((0, 1))["profile"], 0)     # front
        self.assertEqual(self._pose((0, -1))["profile"], 0)    # back

    def test_head_and_shoulder_lean_toward_the_facing(self):
        right = self._pose((1, 0))
        left = self._pose((-1, 0))
        self.assertGreater(right["head"][0], 100)              # head leans right
        self.assertLess(left["head"][0], 100)                 # …and left
        self.assertGreater(right["r_sh"][0], right["l_sh"][0])  # near shoulder front

    def test_side_walk_strides_fore_and_aft(self):
        fwd = cp.build_pose(100, 200, 60, walk=math.pi / 2, moving=True,
                            facing=(1, 0))               # sin > 0
        # the near foot swings forward (+x) while the far foot goes back
        self.assertGreater(fwd["r_foot"][0], fwd["l_foot"][0])


class TestBigBodyRender(unittest.TestCase):
    def test_draw_at_facings_and_states(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((96, 96))
        from ui.body_renderer import draw_body, _ensure_anim
        from ui import char_motion as cm
        from engine.game_engine import GameEngine
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        p = e.player
        surf = pygame.Surface((96, 96))
        for facing, atk, moving in (((0, 1), 0, False), ((0, -1), 0, False),
                                    ((-1, 0), 0, True),
                                    ((0, 1), cm.ATTACK_DUR / 2, False)):
            a = _ensure_anim(p)
            a.update({"facing": facing, "atk_t": atk, "moving": moving,
                      "tween_t": 0.1 if moving else 0.0, "walk_phase": 1.0})
            draw_body(surf, p, 24, 24, 48, is_player=True)   # must not raise
        e.end_game()


if __name__ == "__main__":
    unittest.main()
