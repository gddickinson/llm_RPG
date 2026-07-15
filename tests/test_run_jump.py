"""P34.9 — player RUN & JUMP controls (macOS-safe bindings).

SHIFT+move RUNS in the clear (the run animation + a bonus sprint stride) but stays
the careful DISENGAGE next to a foe; the `` ` `` (backtick) key JUMPS — the jump
animation + a hop forward onto open ground, else a jump in place. Ctrl is NOT used:
macOS grabs it for Spaces / input-source switching (George couldn't run or jump).
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_rj_"))

import unittest

from ui import input_actions as ia


class _Enum:
    def __init__(self, v):
        self.value = v


class _FakePlayer:
    def __init__(self):
        self.metadata = {}
        self.position = (5, 5)


class _Foe:
    def __init__(self, pos):
        self.character_class = _Enum("monster")
        self.position = pos

    def is_active(self):
        return True


class _NPCMgr:
    def __init__(self, foes):
        self.npcs = {i: f for i, f in enumerate(foes)}


class _FakeEngine:
    """Records move_player calls; returns True (moved) up to `ok_moves`."""

    def __init__(self, ok_moves=99, foes=()):
        self.player = _FakePlayer()
        self.calls = []
        self.ok_moves = ok_moves
        self.npc_manager = _NPCMgr(foes)

    def move_player(self, dx, dy, careful=False):
        self.calls.append((dx, dy, careful))
        return len(self.calls) <= self.ok_moves


class _Handler:
    def __init__(self, engine):
        self.engine = engine


class TestStep(unittest.TestCase):
    def test_shift_runs_when_no_foe_adjacent(self):
        e = _FakeEngine()
        ia.step(_Handler(e), 1, 0, shift=True)
        self.assertTrue(e.player.metadata.get("_running"))
        self.assertEqual(len(e.calls), 2)                  # sprint = two strides
        self.assertFalse(e.calls[0][2])                    # not careful in the clear

    def test_plain_move_walks_and_clears_running(self):
        e = _FakeEngine()
        e.player.metadata["_running"] = True
        ia.step(_Handler(e), 1, 0, shift=False)
        self.assertNotIn("_running", e.player.metadata)
        self.assertEqual(len(e.calls), 1)

    def test_shift_is_careful_disengage_next_to_a_foe(self):
        e = _FakeEngine(foes=[_Foe((6, 5))])               # adjacent monster
        ia.step(_Handler(e), 1, 0, shift=True)
        self.assertNotIn("_running", e.player.metadata)    # no run by a foe
        self.assertEqual(len(e.calls), 1)                  # no bonus sprint
        self.assertTrue(e.calls[0][2])                     # careful = True

    def test_run_into_a_wall_does_not_sprint(self):
        e = _FakeEngine(ok_moves=0)                        # first stride blocked
        ia.step(_Handler(e), 1, 0, shift=True)
        self.assertEqual(len(e.calls), 1)


class TestJump(unittest.TestCase):
    def _engine(self, **kw):
        return _FakeEngine(**kw)

    def test_jump_plays_the_animation_and_leaps_forward(self):
        e = _FakeEngine()
        e.player.metadata["_anim"] = {"facing": (1, 0)}
        ia.jump(_Handler(e))
        self.assertEqual(e.player.metadata.get("_emote"), "jump")
        self.assertEqual(e.calls, [(1, 0, False)])

    def test_jump_in_place_when_forward_is_blocked(self):
        e = _FakeEngine(ok_moves=0)
        e.player.metadata["_anim"] = {"facing": (0, 1)}
        ia.jump(_Handler(e))
        self.assertEqual(e.player.metadata.get("_emote"), "jump")
        self.assertEqual(e.calls, [(0, 1, False), (0, 0, False)])


class TestMomentumMoves(unittest.TestCase):
    def _engine(self):
        e = _FakeEngine()
        e.player.metadata["_anim"] = {"facing": (1, 0)}

        class _Mem:
            def add_event(self, m):
                pass
        e.memory_manager = _Mem()
        return e

    def test_jump_with_momentum_is_a_dive_roll(self):
        e = self._engine()
        e.player.metadata["_running"] = True
        ia.jump(_Handler(e))
        self.assertEqual(e.player.metadata.get("_emote"), "roll")
        self.assertEqual(len(e.calls), 2)                 # surges two tiles

    def test_slide_needs_a_running_start(self):
        e = self._engine()
        ia.slide(_Handler(e))                             # no momentum
        self.assertEqual(len(e.calls), 0)                 # nudged, didn't move
        self.assertNotEqual(e.player.metadata.get("_emote"), "slide")

    def test_slide_with_momentum(self):
        e = self._engine()
        e.player.metadata["_running"] = True
        ia.slide(_Handler(e))
        self.assertEqual(e.player.metadata.get("_emote"), "slide")
        self.assertEqual(len(e.calls), 2)


class TestBinding(unittest.TestCase):
    def _handler(self):
        import pygame
        from unittest.mock import MagicMock
        from engine.game_engine import GameEngine
        from ui.input_handler import InputHandler
        engine = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        engine.start_game()
        gui = MagicMock()
        gui.mode = "play"
        gui.overlay = None
        gui.inventory_panel = None
        gui.shop_panel = None
        return engine, InputHandler(engine, gui)

    def test_backtick_routes_to_jump(self):
        import pygame
        engine, handler = self._handler()

        class Ev:
            type = pygame.KEYDOWN
            key = pygame.K_BACKQUOTE
            mod = 0
            unicode = ""

        handler.handle_event(Ev())
        self.assertEqual(engine.player.metadata.get("_emote"), "jump")
        engine.end_game()

    def test_shift_move_flags_running_in_the_clear(self):
        import pygame
        engine, handler = self._handler()
        # clear any hostiles so SHIFT means RUN (spawn is a safe town anyway)
        for nid in list(engine.npc_manager.npcs):
            npc = engine.npc_manager.npcs[nid]
            if getattr(npc.character_class, "value", "") in (
                    "brigand", "monster", "troll"):
                engine.npc_manager.remove_npc(nid)

        class Ev:
            type = pygame.KEYDOWN
            key = pygame.K_d
            mod = pygame.KMOD_SHIFT
            unicode = ""

        handler.handle_event(Ev())
        self.assertTrue(engine.player.metadata.get("_running"))
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
