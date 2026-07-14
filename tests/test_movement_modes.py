"""P34.12 — held-to-move (key repeat) + pace modes (walk / jog / crawl)."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_mm_"))

import unittest
import pygame

from ui import input_actions as ia


class _Mem:
    def add_event(self, msg):
        pass


class _Player:
    def __init__(self):
        self.metadata = {}
        self.position = (5, 5)


class _NPCMgr:
    def __init__(self):
        self.npcs = {}


class _Engine:
    def __init__(self):
        self.player = _Player()
        self.calls = []
        self.npc_manager = _NPCMgr()
        self.memory_manager = _Mem()

    def move_player(self, dx, dy, careful=False):
        self.calls.append((dx, dy, careful))
        return True


class _Handler:
    def __init__(self, engine):
        self.engine = engine


class _Keys:
    def __init__(self, held=()):
        self.held = set(held)

    def __getitem__(self, k):
        return k in self.held


class TestPaceModes(unittest.TestCase):
    def test_cycle_walk_jog_crawl(self):
        h = _Handler(_Engine())
        md = h.engine.player.metadata
        self.assertIsNone(md.get("_move_mode"))
        ia.cycle_move_mode(h)
        self.assertEqual(md["_move_mode"], "jog")
        ia.cycle_move_mode(h)
        self.assertEqual(md["_move_mode"], "crawl")
        ia.cycle_move_mode(h)
        self.assertNotIn("_move_mode", md)            # back to walk

    def test_crawl_step_never_sprints(self):
        e = _Engine()
        e.player.metadata["_move_mode"] = "crawl"
        ia.step(_Handler(e), 1, 0, shift=True)        # shift ignored while prone
        self.assertNotIn("_running", e.player.metadata)
        self.assertEqual(len(e.calls), 1)


class TestAutoWalk(unittest.TestCase):
    def setUp(self):
        self._gp, self._gt = pygame.key.get_pressed, pygame.time.get_ticks

    def tearDown(self):
        pygame.key.get_pressed, pygame.time.get_ticks = self._gp, self._gt

    def _drive(self, keys, t):
        pygame.key.get_pressed = lambda: keys
        pygame.time.get_ticks = lambda: t

    def test_hold_repeats_after_the_delay(self):
        e = _Engine()
        h = _Handler(e)
        self._drive(_Keys([pygame.K_d]), 1000)
        self.assertFalse(ia.auto_walk(h))             # frame 1: arm, no step
        self._drive(_Keys([pygame.K_d]), 1100)
        self.assertFalse(ia.auto_walk(h))             # still within the delay
        self._drive(_Keys([pygame.K_d]), 1300)
        self.assertTrue(ia.auto_walk(h))              # past the delay → a step
        self.assertEqual(e.calls[-1][:2], (1, 0))

    def test_no_key_no_step(self):
        e = _Engine()
        self._drive(_Keys([]), 5000)
        self.assertFalse(ia.auto_walk(_Handler(e)))
        self.assertEqual(e.calls, [])

    def test_changing_direction_rearms_the_delay(self):
        e = _Engine()
        h = _Handler(e)
        self._drive(_Keys([pygame.K_d]), 1000)
        ia.auto_walk(h)                               # arm east
        self._drive(_Keys([pygame.K_w]), 1300)
        self.assertFalse(ia.auto_walk(h))             # new dir → rearm, no step
        self._drive(_Keys([pygame.K_w]), 1550)
        self.assertTrue(ia.auto_walk(h))
        self.assertEqual(e.calls[-1][:2], (0, -1))

    def test_diagonal_from_two_keys(self):
        e = _Engine()
        h = _Handler(e)
        self._drive(_Keys([pygame.K_d, pygame.K_s]), 2000)
        ia.auto_walk(h)                               # arm SE
        self._drive(_Keys([pygame.K_d, pygame.K_s]), 2300)
        self.assertTrue(ia.auto_walk(h))
        self.assertEqual(e.calls[-1][:2], (1, 1))


if __name__ == "__main__":
    unittest.main()
