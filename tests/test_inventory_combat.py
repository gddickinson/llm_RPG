"""Tests for inventory-driven combat: weapon required, ammo, AC, bonuses."""

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


class TestEquipmentBonuses(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_ring_strength_boost(self):
        from engine.effects import effective_stat
        p = self.engine.player
        base = p.strength
        ring = create_item("ring_strength")
        p.inventory.append(ring)
        from characters.equipment import equip
        equip(p, ring)
        self.assertEqual(effective_stat(p, "strength"), base + 2)

    def test_amulet_max_hp(self):
        from engine.effects import effective_max_hp
        p = self.engine.player
        base = p.max_hp
        amulet = create_item("amulet_health")
        p.inventory.append(amulet)
        from characters.equipment import equip
        equip(p, amulet)
        self.assertGreater(effective_max_hp(p), base)

    def test_effective_ac(self):
        from engine.effects import effective_ac
        p = self.engine.player
        # Equip plate + iron_shield + ring_protection
        for item_id in ("plate", "iron_shield", "ring_protection"):
            it = create_item(item_id)
            p.inventory.append(it)
            from characters.equipment import equip
            equip(p, it)
        # AC should be > 10 (base) + DEX_mod
        self.assertGreater(effective_ac(p), 14)


class TestRangedRequiresWeaponAndAmmo(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _strip_equipment(self):
        # Move every equipped item back to the bag
        from characters.equipment import EquipSlot, unequip
        for slot in EquipSlot:
            unequip(self.engine.player, slot)

    def test_shoot_without_ranged_weapon(self):
        self._strip_equipment()
        msg = self.engine.shoot_ranged()
        self.assertIn("no ranged", msg.lower())

    def test_shoot_without_ammo(self):
        self._strip_equipment()
        # Equip a bow but no arrows
        bow = create_item("bow")
        self.engine.player.inventory = [bow]
        from characters.equipment import equip
        equip(self.engine.player, bow)
        # Make sure no arrows
        self.engine.player.inventory = [it for it in
                                        self.engine.player.inventory
                                        if not (hasattr(it, "is_ammo") and
                                                it.is_ammo())]
        msg = self.engine.shoot_ranged()
        self.assertIn("out of", msg.lower())

    def test_shoot_consumes_arrow(self):
        self._strip_equipment()
        bow = create_item("bow")
        arrows = create_item("arrow", quantity=5)
        self.engine.player.inventory = [bow, arrows]
        from characters.equipment import equip
        equip(self.engine.player, bow)
        # Place a hostile in range
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 3,
                                       troll.position[1])
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        before = arrows.quantity
        self.engine.shoot_ranged()
        self.assertEqual(arrows.quantity, before - 1)


class TestMeleeWithoutWeapon(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_unarmed_still_attacks(self):
        # Strip all weapons; placing player adjacent to troll
        from characters.equipment import EquipSlot, unequip
        unequip(self.engine.player, EquipSlot.WEAPON)
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 1,
                                       troll.position[1])
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        # Just ensure it returns a string without crashing
        result = self.engine.combat_system.player_attack(troll.name)
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
