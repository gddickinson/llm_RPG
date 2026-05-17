"""Tests for the banking system."""

import unittest

from engine.game_engine import GameEngine


class TestBanking(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _move_to_temple(self):
        for loc in self.engine.world.locations:
            if "temple" in loc.name.lower():
                cx, cy = loc.center()
                # Place player inside the location bounds
                self.engine.player.position = (cx, cy)
                return True
        return False

    def test_deposit_requires_bank_location(self):
        # Move to a clearly non-bank tile (grass wilderness)
        self.engine.player.position = (0, 0)
        msg = self.engine.deposit_gold(10)
        self.assertIn("only", msg.lower())

    def test_deposit_and_withdraw(self):
        ok = self._move_to_temple()
        self.assertTrue(ok)
        self.engine.player.gold = 100
        msg = self.engine.deposit_gold(40)
        self.assertIn("deposit", msg.lower())
        self.assertEqual(self.engine.player.gold, 60)
        self.assertEqual(self.engine.bank_balance(), 40)
        msg = self.engine.withdraw_gold(20)
        self.assertIn("withdraw", msg.lower())
        self.assertEqual(self.engine.player.gold, 80)
        self.assertEqual(self.engine.bank_balance(), 20)

    def test_overdraw(self):
        self._move_to_temple()
        msg = self.engine.withdraw_gold(1000)
        self.assertIn("only", msg.lower())


if __name__ == "__main__":
    unittest.main()
