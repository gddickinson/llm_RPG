"""Transmute tests (P13.1): the universal value floor."""

import unittest

from engine.game_engine import GameEngine
from engine.item_use import (TRANSMUTE_MANA, TRANSMUTE_RATE,
                             transmute_item)
from items.item_registry import create_item


class TestTransmute(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.player.metadata["spells_known"] = ["transmute"]
        self.player.metadata["mana"] = 20
        self.player.metadata["max_mana"] = 20

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_the_floor_is_forty_percent(self):
        sword = create_item("sword")          # value 30
        self.player.inventory.append(sword)
        gold0 = self.player.gold
        msg = transmute_item(self.engine, sword)
        self.assertIn("hardens into 12g", msg)
        self.assertEqual(self.player.gold, gold0 + 12)
        # identity, not equality — the starting sword EQUALS this one
        self.assertFalse(any(it is sword
                             for it in self.player.inventory))
        self.assertEqual(self.player.metadata["mana"],
                         20 - TRANSMUTE_MANA)

    def test_junk_still_makes_one_coin(self):
        junk = create_item("bread")
        junk.value = 1
        self.player.inventory.append(junk)
        gold0 = self.player.gold
        transmute_item(self.engine, junk)
        self.assertEqual(self.player.gold, gold0 + 1,
                         "the floor never pays zero")

    def test_the_working_must_be_known(self):
        self.player.metadata["spells_known"] = []
        loot = create_item("sword")
        self.player.inventory.append(loot)
        msg = transmute_item(self.engine, loot)
        self.assertIn("don't know", msg)
        self.assertIn(loot, self.player.inventory)

    def test_mana_gates_the_working(self):
        self.player.metadata["mana"] = TRANSMUTE_MANA - 1
        loot = create_item("sword")
        self.player.inventory.append(loot)
        msg = transmute_item(self.engine, loot)
        self.assertIn("needs", msg)
        self.assertIn(loot, self.player.inventory)

    def test_stacks_transmute_one_at_a_time(self):
        ale = create_item("ale", quantity=3)
        self.player.inventory.append(ale)
        transmute_item(self.engine, ale)
        self.assertEqual(ale.quantity, 2)
        self.assertIn(ale, self.player.inventory)

    def test_wizards_know_it_from_the_start(self):
        from engine.spells import SPELL_REGISTRY, starting_spells_for
        self.assertIn("transmute", SPELL_REGISTRY)
        self.assertIn("transmute",
                      [s.id for s in starting_spells_for("wizard")])


if __name__ == "__main__":
    unittest.main()
