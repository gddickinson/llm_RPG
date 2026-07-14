"""P34.3 — secondary motion: springs, look direction, easing."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_cs_"))

import unittest

from ui import char_secondary as cs


class TestSpring(unittest.TestCase):
    def test_converges_to_target(self):
        x, y, vx, vy = 0.0, 0.0, 0.0, 0.0
        for _ in range(120):
            x, y, vx, vy = cs.spring2(x, y, vx, vy, 10.0, -5.0, 1 / 30.0)
        self.assertAlmostEqual(x, 10.0, delta=0.3)
        self.assertAlmostEqual(y, -5.0, delta=0.3)
        self.assertAlmostEqual(vx, 0.0, delta=0.5)     # velocity settles

    def test_lags_before_it_arrives(self):
        # one step from rest doesn't teleport to the target
        x, y, vx, vy = cs.spring2(0.0, 0.0, 0.0, 0.0, 100.0, 0.0, 1 / 30.0)
        self.assertLess(x, 100.0)
        self.assertGreater(x, 0.0)


class TestLook(unittest.TestCase):
    def test_direction_toward_target_and_clamped(self):
        dx, dy = cs.look_dir((5, 5), (15, 5))          # due east
        self.assertGreater(dx, 0.9)
        self.assertAlmostEqual(dy, 0.0, delta=0.01)
        for a in ((0, 0), (100, 0), (-3, 40), (2, -9)):
            ddx, ddy = cs.look_dir((0, 0), a)
            self.assertTrue(-1.0 <= ddx <= 1.0 and -1.0 <= ddy <= 1.0)

    def test_vertical_cone_compressed(self):
        dx, dy = cs.look_dir((0, 0), (0, 10))          # due south
        self.assertLessEqual(abs(dy), 0.66)            # cone_y ≈ 0.65

    def test_ease_moves_toward_want(self):
        cur = (0.0, 0.0)
        for _ in range(40):
            cur = cs.ease2(cur, (1.0, -1.0), 0.15)
        self.assertAlmostEqual(cur[0], 1.0, delta=0.05)
        self.assertAlmostEqual(cur[1], -1.0, delta=0.05)


class TestLookHook(unittest.TestCase):
    def test_update_look_glances_at_nearest(self):
        from engine.game_engine import GameEngine
        from engine import anim
        from world.monsters import build_monster
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        p = e.player
        for nid in list(e.npc_manager.npcs):       # clear the town so the wolf
            e.npc_manager.remove_npc(nid)          # is unambiguously nearest
        px, py = p.position
        foe = build_monster("wolf", (px + 2, py))
        e.npc_manager.add_npc(foe)
        e.world.map.place_character(foe, px + 2, py)
        anim.update_look(e)
        self.assertEqual(tuple(p.metadata.get("_look")), (px + 2, py))
        e.end_game()


if __name__ == "__main__":
    unittest.main()
