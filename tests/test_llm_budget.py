"""LLM cost-discipline tests (P3.9)."""

import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from engine.llm_budget import (llm_action_allowed, ACTION_COOLDOWN_MIN,
                               cached_greeting, GREETING_TTL_MIN)


class TestActionBudget(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.goren = self.engine.npc_manager.get_npc("tavernkeeper_01")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _pretend_llm(self):
        self.engine.llm_interface.provider_name = "anthropic"

    def test_heuristic_provider_never_throttled(self):
        for _ in range(5):
            self.assertTrue(llm_action_allowed(self.engine, self.goren))

    def test_spawned_monsters_never_get_llm_minds(self):
        self._pretend_llm()
        from world.monsters import build_monster
        wolf = build_monster("wolf", (5, 5))
        self.assertFalse(llm_action_allowed(self.engine, wolf))

    def test_named_npc_cooldown(self):
        self._pretend_llm()
        self.assertTrue(llm_action_allowed(self.engine, self.goren))
        self.assertFalse(llm_action_allowed(self.engine, self.goren),
                         "second grant inside the cooldown window")
        self.engine.world.time += ACTION_COOLDOWN_MIN + 1
        self.assertTrue(llm_action_allowed(self.engine, self.goren))

    def test_sync_turn_uses_heuristic_for_throttled_npcs(self):
        self._pretend_llm()
        spy = MagicMock(return_value={"action": "wait", "target": "",
                                      "dialog": "", "thoughts": "",
                                      "emotion": "", "goal_update": ""})
        self.engine.llm_interface.get_npc_action = spy
        # Stamp everyone as recently-served so LLM must not be called
        for npc in self.engine.npc_manager.npcs.values():
            npc.metadata["last_llm_action"] = self.engine.world.time
        self.engine.turn_counter = 0  # % NPC_ACTION_INTERVAL == 0
        self.engine.process_npc_turns()
        spy.assert_not_called()

    def test_call_counters_increment(self):
        counts = self.engine.llm_interface.call_counts
        base = counts["dialog"]
        self.engine.llm_interface.generate_npc_dialog(
            self.goren, "hi", [])
        self.assertEqual(counts["dialog"], base + 1)


class TestGreetingCache(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        px, py = self.engine.player.position
        self.goren.position = (px + 1, py)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_greeting_generated_once_within_ttl(self):
        spy = MagicMock(return_value="Well met, friend!")
        self.engine.llm_interface.generate_npc_dialog = spy
        self.engine.dialog_system.player_to_npc(self.goren.id)
        self.engine.dialog_system.player_to_npc(self.goren.id)
        self.assertEqual(spy.call_count, 1,
                         "second greet inside TTL must hit the cache")
        self.assertEqual(cached_greeting(self.engine, self.goren),
                         "Well met, friend!")

    def test_greeting_regenerates_after_ttl(self):
        spy = MagicMock(return_value="Well met!")
        self.engine.llm_interface.generate_npc_dialog = spy
        self.engine.dialog_system.player_to_npc(self.goren.id)
        self.engine.world.time += GREETING_TTL_MIN + 1
        self.engine.dialog_system.player_to_npc(self.goren.id)
        self.assertEqual(spy.call_count, 2)

    def test_real_messages_never_cached(self):
        spy = MagicMock(return_value="Aye, the troll's a menace.")
        self.engine.llm_interface.generate_npc_dialog = spy
        self.engine.dialog_system.player_to_npc(self.goren.id, "Troll?")
        self.engine.dialog_system.player_to_npc(self.goren.id, "Troll?")
        self.assertEqual(spy.call_count, 2,
                         "actual conversation must never be cached")


if __name__ == "__main__":
    unittest.main()
