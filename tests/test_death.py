"""Tests for the player-death flag and restart flow."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))


import unittest

from engine.game_engine import GameEngine


class TestPlayerDeath(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.engine._has_gui = True  # simulate GUI presence
        # P4.7 made overworld defeat usually survivable; these tests
        # cover the FINAL outcome, so force the slain roll (< 0.10)
        self.engine.combat_system.rng.random = lambda: 0.05

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_player_dead_flag_starts_false(self):
        self.assertFalse(self.engine.player_dead)

    def test_a_lethal_beating_is_survivable_now(self):
        # soulslike: no matter how hard the troll hits, the player never
        # permanently dies — they bottom out the dying ladder and wake at
        # sanctuary with a bloodstain (never the game-over flag)
        from engine.checkpoint import has_bloodstain
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 1, troll.position[1])
        self.engine.world.map.place_character(
            self.engine.player, *self.engine.player.position)
        self.engine.player.hp = 1
        for _ in range(60):
            self.engine.combat_system._resolve(troll, self.engine.player)
            if has_bloodstain(self.engine):
                break
        self.assertFalse(self.engine.player_dead,
                         "death is never terminal now")
        self.assertTrue(self.engine.running, "the game goes on")

    def test_no_immediate_engine_shutdown_with_gui(self):
        # With _has_gui, death should NOT call end_game()
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 1, troll.position[1])
        self.engine.world.map.place_character(
            self.engine.player, *self.engine.player.position)
        self.engine.player.hp = 1
        for _ in range(50):
            if self.engine.player_dead:
                break
            self.engine.combat_system._resolve(troll, self.engine.player)
            if not self.engine.player.is_alive():
                break
        # Engine should still be `running` so the GUI can render the popup
        self.assertTrue(self.engine.running)

    def test_headless_fall_does_not_end_the_game(self):
        # even headless (no GUI), a lethal fall is a soulslike recovery,
        # not an end_game — the run continues
        from engine.checkpoint import has_bloodstain
        self.engine._has_gui = False
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 1, troll.position[1])
        self.engine.world.map.place_character(
            self.engine.player, *self.engine.player.position)
        self.engine.player.hp = 1
        for _ in range(60):
            self.engine.combat_system._resolve(troll, self.engine.player)
            if has_bloodstain(self.engine):
                break
        self.assertFalse(self.engine.player_dead)
        self.assertTrue(self.engine.running)


if __name__ == "__main__":
    unittest.main()
