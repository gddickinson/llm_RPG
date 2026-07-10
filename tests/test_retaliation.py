"""Retaliation tests (P7.2) — the player can make a real enemy."""

import unittest

from engine.game_engine import GameEngine
from engine.retaliation import (THRESHOLD, DEEP, COOLDOWN_DAYS,
                                SPAWN_MIN)
from characters.factions import Faction, set_rep


class TestRetaliation(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.system = self.engine.retaliation

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _hunters(self):
        return [n for n in self.engine.npc_manager.npcs.values()
                if n.metadata.get("bounty_hunter") and n.is_active()]

    def _night(self, day_offset=0):
        self.engine.world.time = \
            (self.engine.world.time // (24 * 60) + day_offset) * 24 * 60
        return self.system.run_night()

    def test_neutral_player_is_never_hunted(self):
        notes = self._night()
        self.assertEqual(notes, [])
        self.assertEqual(self._hunters(), [])

    def test_warning_always_precedes_the_hunt(self):
        set_rep(self.engine.player, Faction.BRIGANDS, THRESHOLD - 5)
        notes = self._night(1)
        self.assertTrue(any("price on your head" in n for n in notes))
        self.assertEqual(self._hunters(), [],
                         "no ambush without a warning first")

    def test_hunter_sent_after_warning_and_cooldown(self):
        set_rep(self.engine.player, Faction.BRIGANDS, THRESHOLD - 5)
        self._night(1)                       # the warning
        self._night(COOLDOWN_DAYS)           # the hunt
        hunters = self._hunters()
        self.assertEqual(len(hunters), 1)
        px, py = self.engine.player.position
        hx, hy = hunters[0].position
        self.assertGreaterEqual(abs(hx - px) + abs(hy - py), SPAWN_MIN)
        self.assertEqual(hunters[0].metadata.get("alert"), [px, py])

    def test_deep_hostility_sends_a_pair(self):
        set_rep(self.engine.player, Faction.GUARDS, DEEP - 5)
        self._night(1)
        self._night(COOLDOWN_DAYS)
        self.assertEqual(len(self._hunters()), 2)

    def test_cooldown_prevents_nightly_spam(self):
        set_rep(self.engine.player, Faction.BRIGANDS, THRESHOLD - 5)
        self._night(1)
        self._night(COOLDOWN_DAYS)
        self._night(1)                       # too soon
        self.assertEqual(len(self._hunters()), 1)

    def test_recovered_reputation_stands_the_hunt_down(self):
        set_rep(self.engine.player, Faction.BRIGANDS, THRESHOLD - 5)
        self._night(1)                       # warned (stage 1)
        set_rep(self.engine.player, Faction.BRIGANDS, 0)
        notes = self._night(COOLDOWN_DAYS)
        self.assertEqual(notes, [])
        self.assertEqual(self._hunters(), [])
        self.assertEqual(
            self.system.state[Faction.BRIGANDS.value]["stage"], 0,
            "forgiveness must reset the ladder to the warning stage")

    def test_hunter_is_level_scaled(self):
        self.engine.player.level = 5
        set_rep(self.engine.player, Faction.BRIGANDS, THRESHOLD - 5)
        self._night(1)
        self._night(COOLDOWN_DAYS)
        hunter = self._hunters()[0]
        self.assertEqual(hunter.level, 5)
        self.assertGreater(hunter.max_hp, 16)

    def test_state_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        set_rep(self.engine.player, Faction.BRIGANDS, THRESHOLD - 5)
        self._night(1)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="ret")
            self.system.state = {}
            self.assertTrue(sm.load(self.engine, name="ret"))
            self.assertEqual(
                self.engine.retaliation
                .state[Faction.BRIGANDS.value]["stage"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_nightly_stack_runs_it(self):
        set_rep(self.engine.player, Faction.BRIGANDS, THRESHOLD - 5)
        now = self.engine.world.time
        self.engine.world.time = ((now // (24 * 60)) + 1) * 24 * 60
        self.engine.advance_turn()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-25:])
        self.assertIn("price on your head", log)


if __name__ == "__main__":
    unittest.main()
