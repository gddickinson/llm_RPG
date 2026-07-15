"""P34.16 — run stamina & tiring: pool, drain, winded, recovery, bypass."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_stam_"))

import unittest

from engine import stamina


class _Char:
    def __init__(self, con=10):
        self.constitution = con
        self.metadata = {}


class TestModel(unittest.TestCase):
    def test_pool_scales_with_constitution(self):
        self.assertGreater(stamina.max_stamina(_Char(con=18)),
                           stamina.max_stamina(_Char(con=8)))

    def test_sprint_drains_then_winds(self):
        c = _Char()
        start = stamina.get(c)
        stamina.spend(c)
        self.assertLess(stamina.get(c), start)
        # empty it out
        for _ in range(60):
            stamina.spend(c)
        self.assertTrue(stamina.is_winded(c))
        self.assertFalse(stamina.can_run(c))          # can't sprint while winded

    def test_recovery_clears_winded_with_hysteresis(self):
        c = _Char()
        for _ in range(60):
            stamina.spend(c)
        self.assertTrue(stamina.is_winded(c))
        # a couple of turns isn't enough (must reach RECOVER)
        stamina.recover(c)
        self.assertTrue(stamina.is_winded(c))
        for _ in range(20):
            stamina.recover(c)
        self.assertFalse(stamina.is_winded(c))
        self.assertTrue(stamina.can_run(c))

    def test_tireless_never_drains(self):
        c = _Char()
        c.metadata["tireless"] = True
        for _ in range(30):
            stamina.spend(c)
        self.assertFalse(stamina.is_winded(c))
        self.assertTrue(stamina.can_run(c))

    def test_leg_injury_tires_faster(self):
        base = stamina.drain_mult(_Char())
        hurt = _Char()
        hurt.metadata["wounds"] = {"legs": 3}      # wounds.severity reads this
        self.assertGreater(stamina.drain_mult(hurt), base)


class TestExertion(unittest.TestCase):
    def test_fresh_body_has_no_penalty(self):
        self.assertEqual(stamina.exertion_penalty(_Char()), 0)   # existing balance

    def test_gassed_body_is_penalised(self):
        c = _Char()
        for _ in range(60):
            stamina.spend_action(c, 5.0)
        self.assertGreater(stamina.exertion_penalty(c), 0)       # winded → penalty

    def test_spend_action_respects_tireless(self):
        c = _Char()
        c.metadata["tireless"] = True
        for _ in range(40):
            stamina.spend_action(c, 5.0)
        self.assertFalse(stamina.is_winded(c))
        self.assertEqual(stamina.exertion_penalty(c), 0)


class TestStepGate(unittest.TestCase):
    def test_winded_hero_cannot_sprint(self):
        from ui import input_actions as ia

        class _Eng:
            def __init__(self):
                self.player = _Char()
                self.player.position = (5, 5)
                self.calls = []

                class _NPC:
                    npcs = {}
                self.npc_manager = _NPC()

                class _Mem:
                    def add_event(self, m):
                        pass
                self.memory_manager = _Mem()

            def move_player(self, dx, dy, careful=False):
                self.calls.append((dx, dy, careful))
                return True

        class _H:
            def __init__(self, e):
                self.engine = e

        e = _Eng()
        e.player.metadata["_winded"] = True
        e.player.metadata["run_stamina"] = 5.0
        ia.step(_H(e), 1, 0, shift=True)
        self.assertNotIn("_running", e.player.metadata)     # no sprint while winded
        self.assertEqual(len(e.calls), 1)                   # a single walk step


class TestPersistence(unittest.TestCase):
    def test_stamina_rides_the_metadata(self):
        c = _Char()
        stamina.spend(c)
        val = stamina.get(c)
        # metadata is what save/load round-trips
        self.assertIn("run_stamina", c.metadata)
        self.assertEqual(c.metadata["run_stamina"], val)


if __name__ == "__main__":
    unittest.main()
