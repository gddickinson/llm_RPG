"""Structured dialog protocol tests (P3.1) — no real LLM needed."""

import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from engine.dialog_protocol import (parse_response, execute_action,
                                    build_prompt, run_dialog)
from items.item_registry import create_item


class TestParsing(unittest.TestCase):
    def test_clean_json(self):
        parsed = parse_response(
            '{"dialogue": "Well met!", "mood": "cheerful", '
            '"action": "adjust_affinity", "action_args": {"delta": 2}}')
        self.assertEqual(parsed["dialogue"], "Well met!")
        self.assertEqual(parsed["action"], "adjust_affinity")
        self.assertEqual(parsed["action_args"]["delta"], 2)

    def test_json_in_markdown_fences_with_chatter(self):
        raw = ("Here is my response:\n```json\n"
               '{"dialogue": "Hmm.", "mood": "wary"}\n```\nHope that helps!')
        parsed = parse_response(raw)
        self.assertEqual(parsed["dialogue"], "Hmm.")
        self.assertEqual(parsed["action"], "")

    def test_plain_prose_becomes_dialogue(self):
        parsed = parse_response("Good morrow to you, traveler.")
        self.assertEqual(parsed["dialogue"],
                         "Good morrow to you, traveler.")
        self.assertEqual(parsed["action"], "")

    def test_invalid_json_falls_back_to_raw(self):
        raw = '{"dialogue": "broken...'
        parsed = parse_response(raw)
        self.assertEqual(parsed["dialogue"], raw)

    def test_unknown_action_stripped(self):
        parsed = parse_response(
            '{"dialogue": "Die!", "action": "attack_player", '
            '"action_args": {}}')
        self.assertEqual(parsed["action"], "",
                         "non-whitelisted actions must be stripped")

    def test_empty_response(self):
        self.assertEqual(parse_response("")["dialogue"], "...")


class TestActions(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
        if self.npc is None:
            self.skipTest("Goren missing")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_affinity_delta_applied_and_clamped(self):
        before = self.npc.get_relationship(self.player.id)
        execute_action(self.engine, self.npc, {
            "action": "adjust_affinity", "action_args": {"delta": 50}})
        self.assertEqual(self.npc.get_relationship(self.player.id),
                         before + 3, "delta must clamp to +-3")

    def test_give_item_only_from_npc_inventory(self):
        ale = create_item("ale")
        self.npc.inventory = [ale]
        note = execute_action(self.engine, self.npc, {
            "action": "give_item", "action_args": {"item_id": "ale"}})
        self.assertIn("hands you", note)
        self.assertIn(ale, self.player.inventory)
        self.assertNotIn(ale, self.npc.inventory)
        # Hallucinated item: no transfer, no crash
        note = execute_action(self.engine, self.npc, {
            "action": "give_item",
            "action_args": {"item_id": "dragon_slayer_9000"}})
        self.assertIsNone(note)

    def test_bad_args_do_not_crash(self):
        self.assertIsNone(execute_action(self.engine, self.npc, {
            "action": "adjust_affinity",
            "action_args": {"delta": "lots"}}))

    def test_prompt_contains_facts_not_fiction(self):
        self.npc.inventory = [create_item("ale")]
        prompt = build_prompt(self.engine, self.npc, "Hello!", [])
        self.assertIn("Goren", prompt)
        self.assertIn("'ale'", prompt)
        self.assertIn("SAYS: \"Hello!\"", prompt)


class TestRouting(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.npc = self.engine.npc_manager.get_npc("tavernkeeper_01")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_heuristic_provider_skips_protocol(self):
        self.assertIsNone(
            run_dialog(self.engine, self.npc, "Hi", []))

    def test_llm_provider_uses_protocol_end_to_end(self):
        # Fake an LLM provider on the interface
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value='{"dialogue": "A fine day for ale!", '
                         '"mood": "jolly", "action": "adjust_affinity", '
                         '"action_args": {"delta": 1}}')
        before = self.npc.get_relationship(self.engine.player.id)
        px, py = self.engine.player.position
        self.npc.position = (px + 1, py)
        reply = self.engine.dialog_system.player_to_npc(
            self.npc.id, "Hello Goren!")
        self.assertIn("A fine day for ale!", reply)
        # +1 from the LLM action, +2 from the friendly-chat bonus
        self.assertEqual(
            self.npc.get_relationship(self.engine.player.id), before + 3)
        self.engine.llm_interface.generate_response.assert_called_once()

    def test_give_item_note_reaches_event_log(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.npc.inventory = [create_item("ale")]
        self.engine.llm_interface.generate_response = MagicMock(
            return_value='{"dialogue": "On the house!", '
                         '"action": "give_item", '
                         '"action_args": {"item_id": "ale"}}')
        px, py = self.engine.player.position
        self.npc.position = (px + 1, py)
        self.engine.dialog_system.player_to_npc(self.npc.id, "I'm thirsty")
        ids = [getattr(i, "id", "") for i in self.engine.player.inventory]
        self.assertIn("ale", ids)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-10:])
        self.assertIn("hands you", log)


if __name__ == "__main__":
    unittest.main()
