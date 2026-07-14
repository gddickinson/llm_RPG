"""P34.9 — player RUN & JUMP controls.

CTRL+move sprints (the run animation + a bonus stride); a plain move walks (and
clears the run flag); CTRL+SPACE leaps (the jump animation + a hop forward, else
a jump in place). The helpers live in `ui.input_actions`; the binding is wired in
`ui.input_handler`.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_rj_"))

import unittest

from ui import input_actions as ia


class _FakePlayer:
    def __init__(self):
        self.metadata = {}
        self.position = (5, 5)


class _FakeEngine:
    """Records move_player calls; returns True (moved) up to `ok_moves`."""

    def __init__(self, ok_moves=99):
        self.player = _FakePlayer()
        self.calls = []
        self.ok_moves = ok_moves

    def move_player(self, dx, dy, careful=False):
        self.calls.append((dx, dy, careful))
        return len(self.calls) <= self.ok_moves


class _Handler:
    def __init__(self, engine):
        self.engine = engine


class TestStep(unittest.TestCase):
    def test_run_sprints_a_bonus_tile_and_flags_running(self):
        e = _FakeEngine()
        ia.step(_Handler(e), 1, 0, careful=False, run=True)
        self.assertTrue(e.player.metadata.get("_running"))
        self.assertEqual(len(e.calls), 2)          # a running stride covers 2

    def test_walk_moves_once_and_clears_running(self):
        e = _FakeEngine()
        e.player.metadata["_running"] = True       # left over from a prior run
        ia.step(_Handler(e), 1, 0, careful=False, run=False)
        self.assertNotIn("_running", e.player.metadata)
        self.assertEqual(len(e.calls), 1)

    def test_run_into_a_wall_does_not_sprint(self):
        e = _FakeEngine(ok_moves=0)                # the first stride is blocked
        ia.step(_Handler(e), 1, 0, careful=False, run=True)
        self.assertEqual(len(e.calls), 1)          # no bonus stride when blocked

    def test_careful_flag_passes_through(self):
        e = _FakeEngine()
        ia.step(_Handler(e), 0, -1, careful=True, run=False)
        self.assertEqual(e.calls[0], (0, -1, True))


class TestJump(unittest.TestCase):
    def test_jump_plays_the_animation_and_leaps_forward(self):
        e = _FakeEngine()
        e.player.metadata["_anim"] = {"facing": (1, 0)}   # facing east
        ia.jump(_Handler(e))
        self.assertEqual(e.player.metadata.get("_emote"), "jump")
        self.assertEqual(e.calls, [(1, 0, False)])        # leapt east one tile

    def test_jump_in_place_when_forward_is_blocked(self):
        e = _FakeEngine(ok_moves=0)                       # forward blocked
        e.player.metadata["_anim"] = {"facing": (0, 1)}
        ia.jump(_Handler(e))
        self.assertEqual(e.player.metadata.get("_emote"), "jump")
        # attempted the forward leap (blocked), then hopped in place
        self.assertEqual(e.calls, [(0, 1, False), (0, 0, False)])


class TestBinding(unittest.TestCase):
    def test_ctrl_space_routes_to_jump(self):
        import pygame
        from unittest.mock import MagicMock
        from engine.game_engine import GameEngine
        from ui.input_handler import InputHandler

        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        gui = MagicMock()
        gui.mode = "play"
        gui.overlay = None
        gui.inventory_panel = None
        gui.shop_panel = None
        handler = InputHandler(engine, gui)

        class Ev:
            type = pygame.KEYDOWN
            key = pygame.K_SPACE
            mod = pygame.KMOD_CTRL
            unicode = ""

        handler.handle_event(Ev())
        # jump requested the leap animation on the player
        self.assertEqual(engine.player.metadata.get("_emote"), "jump")
        engine.end_game()

    def test_ctrl_move_flags_running(self):
        import pygame
        from unittest.mock import MagicMock
        from engine.game_engine import GameEngine
        from ui.input_handler import InputHandler

        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        gui = MagicMock()
        gui.mode = "play"
        gui.overlay = None
        gui.inventory_panel = None
        gui.shop_panel = None
        handler = InputHandler(engine, gui)

        class Ev:
            type = pygame.KEYDOWN
            key = pygame.K_d
            mod = pygame.KMOD_CTRL
            unicode = ""

        handler.handle_event(Ev())
        self.assertTrue(engine.player.metadata.get("_running"))
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
