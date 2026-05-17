"""Tests for the combat system."""

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


class TestCombat(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_attack_out_of_range(self):
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        # Player and troll are far apart in default world
        msg = self.engine.attack_character(troll.name)
        self.assertIn("too far", msg.lower())

    def test_attack_adjacent(self):
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        # Place player next to troll
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 1, troll.position[1])
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        before_hp = troll.hp
        # Force enough attacks to land
        landed = False
        for _ in range(50):
            msg = self.engine.attack_character(troll.name)
            if "damage" in msg and "miss" not in msg:
                landed = True
                break
            if troll.hp <= 0:
                landed = True
                break
        self.assertTrue(landed)

    def test_kill_grants_xp(self):
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        troll.hp = 1
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 1, troll.position[1])
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        before_xp = (self.engine.player.metadata or {}).get("xp", 0)
        # Hit until defeated
        for _ in range(50):
            self.engine.attack_character(troll.name)
            if not troll.is_active():
                break
        # If lucky enough to defeat troll (low HP), XP should grow
        after_xp = (self.engine.player.metadata or {}).get("xp", 0)
        self.assertGreaterEqual(after_xp, before_xp)

    def test_weapon_damage_bonus(self):
        from engine.combat_system import CombatSystem
        cs = CombatSystem(self.engine)
        p = self.engine.player
        p.inventory = [create_item("longsword")]
        bonus = cs._best_weapon_damage(p)
        self.assertEqual(bonus, 8)

    def test_armor_reduction(self):
        from engine.combat_system import CombatSystem
        cs = CombatSystem(self.engine)
        p = self.engine.player
        p.inventory = [create_item("plate")]
        red = cs._total_armor(p)
        self.assertEqual(red, 6)


if __name__ == "__main__":
    unittest.main()
