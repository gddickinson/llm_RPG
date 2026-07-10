"""Tests for the player-death flag and restart flow."""

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

    def test_player_death_sets_flag(self):
        # Drop player HP and have troll defeat them
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 1, troll.position[1])
        self.engine.world.map.place_character(
            self.engine.player, *self.engine.player.position)
        self.engine.player.hp = 1
        # Force the combat system to resolve a kill
        result = self.engine.combat_system._resolve(troll, self.engine.player)
        # The combat may roll a miss; loop a few times to ensure death
        for _ in range(50):
            if self.engine.player_dead:
                break
            self.engine.combat_system._resolve(troll, self.engine.player)
            if not self.engine.player.is_alive():
                break
        self.assertTrue(self.engine.player_dead,
                        "player_dead flag should be set after defeat")

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

    def test_terminal_mode_does_end_game(self):
        # Without _has_gui, combat death should call end_game
        self.engine._has_gui = False
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
        self.assertTrue(self.engine.player_dead)
        self.assertFalse(self.engine.running)


if __name__ == "__main__":
    unittest.main()
