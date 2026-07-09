"""Player hunger — light survival wiring (P0.6).

Hunger grows with time, food satisfies it, starving weakens (never kills).
"""

import unittest

from engine.game_engine import GameEngine
from characters.needs import (get_hunger, hunger_attack_penalty,
                              HUNGER_HUNGRY, HUNGER_STARVING)
from items.item_registry import create_item


class TestPlayerHunger(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_hunger_grows_over_time(self):
        before = get_hunger(self.player)
        for _ in range(120):  # 2 game hours
            self.engine.advance_turn()
        self.assertGreater(get_hunger(self.player), before)

    def test_eating_reduces_hunger_and_heals(self):
        self.player.metadata["hunger"] = 70
        self.player.hp = self.player.max_hp - 10
        self.player.inventory.append(create_item("bread"))
        msg = self.engine.use_item("Bread")
        self.assertIn("consume", msg.lower())
        self.assertLess(get_hunger(self.player), 70)
        self.assertEqual(self.player.hp, self.player.max_hp - 10 + 4)

    def test_can_eat_at_full_hp_when_hungry(self):
        self.player.metadata["hunger"] = 70
        self.player.hp = self.player.max_hp
        self.player.inventory.append(create_item("jerky"))
        msg = self.engine.use_item("Jerky")
        self.assertNotIn("already at full health", msg)
        self.assertLess(get_hunger(self.player), 70)

    def test_full_hp_not_hungry_refuses_food(self):
        self.player.metadata["hunger"] = 0
        self.player.hp = self.player.max_hp
        self.player.inventory.append(create_item("bread"))
        msg = self.engine.use_item("Bread")
        self.assertIn("already at full health", msg)

    def test_starving_drains_hp_but_never_kills(self):
        self.player.metadata["hunger"] = 100
        self.player.hp = 2
        # Align world time so the next turn lands on a %30 drain tick,
        # keeping the test to 2 turns (long sims invite monster attacks)
        self.engine.world.time = 29
        self.engine.advance_turn()
        self.assertEqual(self.player.hp, 1, "one drain tick: 2 -> 1")

        self.player.metadata["hunger"] = 100
        self.engine.world.time = 59
        self.engine.advance_turn()
        self.assertEqual(self.player.hp, 1,
                         "starving drains to 1 HP and stops")

    def test_hunger_attack_penalty_thresholds(self):
        self.player.metadata["hunger"] = 0
        self.assertEqual(hunger_attack_penalty(self.player), 0)
        self.player.metadata["hunger"] = HUNGER_HUNGRY
        self.assertEqual(hunger_attack_penalty(self.player), -1)
        self.player.metadata["hunger"] = HUNGER_STARVING
        self.assertEqual(hunger_attack_penalty(self.player), -2)


if __name__ == "__main__":
    unittest.main()
