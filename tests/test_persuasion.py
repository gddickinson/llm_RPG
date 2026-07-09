"""Persuasion / intimidation / deception with stakes (P3.4)."""

import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from engine.persuasion import parse_command, FAIL_AFFINITY


class TestParsing(unittest.TestCase):
    def test_commands_parse(self):
        self.assertEqual(parse_command("/persuade lower your prices"),
                         ("persuade", "lower your prices"))
        self.assertEqual(parse_command("/INTIMIDATE back off"),
                         ("intimidate", "back off"))
        self.assertIsNone(parse_command("hello there"))
        self.assertIsNone(parse_command("/persuade"))  # no argument


class TestAdjudication(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.ps = self.engine.persuasion

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_heuristic_success_grants_haggle_discount(self):
        self.ps.rng.randint = lambda a, b: 20  # guaranteed roll
        msg = self.ps.attempt(self.goren, "persuade", "friendly prices?")
        self.assertIn("SUCCESS", msg)
        self.assertTrue(self.ps.haggle_active(self.goren))
        # And the shop actually charges less
        from items.item_registry import create_item
        item = create_item("ale")
        discounted = self.engine.shop_manager.buy_price(
            self.player, item, self.goren)
        self.player.metadata["haggle"] = {}
        base = self.engine.shop_manager.buy_price(
            self.player, item, self.goren)
        self.assertLessEqual(discounted, base)

    def test_failure_costs_affinity_and_locks_verb(self):
        self.ps.rng.randint = lambda a, b: 1  # guaranteed fail
        before = self.goren.get_relationship(self.player.id)
        msg = self.ps.attempt(self.goren, "persuade", "gimme stuff")
        self.assertIn("FAILED", msg)
        self.assertEqual(self.goren.get_relationship(self.player.id),
                         before + FAIL_AFFINITY)
        # Locked: even a natural 20 is refused today
        self.ps.rng.randint = lambda a, b: 20
        msg2 = self.ps.attempt(self.goren, "persuade", "please?")
        self.assertIn("no mood", msg2)
        # Other verbs remain available
        msg3 = self.ps.attempt(self.goren, "deceive", "I'm a tax officer")
        self.assertIn("SUCCESS", msg3)

    def test_lock_expires_after_a_day(self):
        self.ps.rng.randint = lambda a, b: 1
        self.ps.attempt(self.goren, "persuade", "x")
        self.engine.world.time += 24 * 60 + 1
        self.assertFalse(self.ps.is_locked(self.goren, "persuade"))

    def test_intimidate_frightens_target(self):
        from characters.status_effects import has_effect
        self.ps.rng.randint = lambda a, b: 20
        self.ps.attempt(self.goren, "intimidate", "step aside")
        self.assertTrue(has_effect(self.goren, "frightened"))

    def test_llm_judge_verdict_used(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value='{"success": true, "reason": "He loves gold '
                         'and your offer was shrewd."}')
        msg = self.ps.attempt(self.goren, "persuade",
                              "I'll send every traveler to your tavern")
        self.assertIn("SUCCESS", msg)
        self.assertIn("shrewd", msg)

    def test_llm_junk_falls_back_to_dice(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value="I cannot judge this.")
        self.ps.rng.randint = lambda a, b: 20
        msg = self.ps.attempt(self.goren, "deceive", "trust me")
        self.assertIn("SUCCESS", msg, "junk verdict should fall to dice")

    def test_dialog_routes_slash_commands(self):
        px, py = self.player.position
        self.goren.position = (px + 1, py)
        self.ps.rng.randint = lambda a, b: 20
        reply = self.engine.dialog_system.player_to_npc(
            self.goren.id, "/persuade your ale is legendary, friend")
        self.assertIn("SUCCESS", reply)

    def test_npc_remembers_the_attempt(self):
        self.ps.rng.randint = lambda a, b: 1
        self.ps.attempt(self.goren, "intimidate", "or else")
        self.assertTrue(any("intimidate" in m.get("event", "")
                            for m in self.goren.memories))

    def test_locks_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.ps.rng.randint = lambda a, b: 1
        self.ps.attempt(self.goren, "persuade", "x")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="pl")
            self.player.metadata["persuasion_locks"] = {}
            self.assertTrue(sm.load(self.engine, name="pl"))
            self.assertTrue(
                self.engine.persuasion.is_locked(self.goren, "persuade"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
