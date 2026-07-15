"""Equipment II tests (P15.10): two-handed rules + set bonuses."""

import unittest

from characters.equipment import (equip, equipped_shield,
                                  equipped_weapon, get_equipment,
                                  set_bonus, unequip, EquipSlot)
from engine.effects import effective_ac
from engine.game_engine import GameEngine
from items.item_registry import create_item


class TestEquipment2(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.player.dexterity = 10   # AC baseline steady
        # clear starting gear for clean assertions
        for s in EquipSlot:
            it = get_equipment(self.player).get(s.value)
            if it:
                unequip(self.player, s)
        self.player.inventory = []

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _give(self, item_id):
        it = create_item(item_id)
        self.player.inventory.append(it)
        return it

    def test_two_handed_stows_the_shield(self):
        shield = self._give("shield")
        equip(self.player, shield)
        self.assertIs(equipped_shield(self.player), shield)
        greataxe = self._give("battleaxe")   # two_handed
        msg = equip(self.player, greataxe)
        self.assertIn("both hands", msg.lower())
        self.assertIsNone(equipped_shield(self.player),
                          "the shield came off for the two-hander")
        self.assertIn(shield, self.player.inventory)

    def test_no_shield_while_two_handed(self):
        greataxe = self._give("warhammer")   # two_handed
        equip(self.player, greataxe)
        shield = self._give("shield")
        msg = equip(self.player, shield)
        self.assertIn("no room for a shield", msg.lower())
        self.assertIsNone(equipped_shield(self.player))
        self.assertIn(shield, self.player.inventory)

    def test_one_handed_keeps_the_shield(self):
        shield = self._give("shield")
        equip(self.player, shield)
        sword = self._give("sword")          # one-handed
        equip(self.player, sword)
        self.assertIs(equipped_shield(self.player), shield,
                      "a one-hander leaves the shield up")
        self.assertIs(equipped_weapon(self.player), sword)

    def test_the_iron_set_rewards_the_matched_pieces(self):
        chain = self._give("chainmail")      # iron set, armor 4
        equip(self.player, chain)
        self.assertEqual(set_bonus(self.player), (0, None),
                         "one piece is no set")
        ac_one = effective_ac(self.player)
        ishield = self._give("iron_shield")  # iron set, armor 3
        equip(self.player, ishield)
        n, name = set_bonus(self.player)
        self.assertEqual((n, name), (2, "iron"))
        ac_two = effective_ac(self.player)
        # +3 shield armor, +2 set bonus over the one-piece AC
        self.assertEqual(ac_two - ac_one, 3 + 2)
        iboots = self._give("iron_boots")
        equip(self.player, iboots)
        self.assertEqual(set_bonus(self.player), (3, "iron"),
                         "three matched pieces, +3 AC")

    def test_a_mismatched_kit_earns_no_set(self):
        equip(self.player, self._give("chainmail"))   # iron
        equip(self.player, self._give("shield"))      # plain
        self.assertEqual(set_bonus(self.player), (0, None))

    def test_the_panel_status_line_reads_the_kit(self):
        equip(self.player, self._give("chainmail"))
        equip(self.player, self._give("iron_shield"))
        from ui.inventory_panel import InventoryPanel
        panel = InventoryPanel(self.engine)
        line = panel._status_line()
        self.assertIn("AC", line)
        self.assertIn("iron set", line)
        self.assertIn("pack", line)


if __name__ == "__main__":
    unittest.main()
