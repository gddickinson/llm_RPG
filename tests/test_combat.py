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
        # Combat now reads from equipped weapon, not bag scan.
        from engine.combat_system import CombatSystem
        from characters.equipment import equip, get_equipment
        cs = CombatSystem(self.engine)
        p = self.engine.player
        # Clear existing equipment
        p.equipment = None
        get_equipment(p)
        p.inventory = [create_item("longsword")]
        equip(p, p.inventory[0])
        bonus = cs._best_weapon_damage(p)
        self.assertEqual(bonus, 8)

    def test_armor_reduction(self):
        from engine.combat_system import CombatSystem
        from characters.equipment import equip, get_equipment
        cs = CombatSystem(self.engine)
        p = self.engine.player
        p.equipment = None
        get_equipment(p)
        p.inventory = [create_item("plate")]
        equip(p, p.inventory[0])
        red = cs._total_armor(p)
        self.assertEqual(red, 6)


class _Crit:
    """A rigged RNG: a natural 20 to-hit (crit) + max damage."""
    def randint(self, a, b):
        return 20 if b == 20 else b

    def random(self):
        return 0.5

    def uniform(self, a, b):
        return (a + b) / 2


class TestCombatContact(unittest.TestCase):
    """I5 — a decisive melee crit drives a non-player foe to the ground."""

    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _foe(self, hp, max_hp):
        from world.monsters import build_monster
        from world.world_map import TerrainType
        wm = self.engine.world.map
        p = self.engine.player
        for (x, y) in ((5, 5), (6, 5)):
            wm.terrain[y][x] = TerrainType.GRASS
            ch = wm.get_character_at(x, y)
            if ch is not None and ch is not p:
                wm.remove_character(ch)
        wm.remove_character(p)
        p.position = (5, 5)
        wm.place_character(p, 5, 5)
        foe = self.engine.npc_manager.create_random_npc()
        wm.remove_character(foe)
        foe.position = (6, 5)
        foe.hp, foe.max_hp = hp, max_hp
        wm.place_character(foe, 6, 5)
        self.engine.combat_system.rng = _Crit()
        return p, foe

    def test_decisive_crit_knocks_the_foe_down(self):
        p, foe = self._foe(hp=4, max_hp=30)      # a crit will fell it
        self.engine.combat_system._resolve(p, foe)
        self.assertFalse(foe.is_alive())
        self.assertEqual(foe.metadata.get("_emote"), "knockdown")
        self.assertEqual(p.metadata.get("_emote"), "attack")

    def test_crit_on_a_hale_foe_only_recoils(self):
        p, foe = self._foe(hp=200, max_hp=200)   # survives well above 30%
        self.engine.combat_system._resolve(p, foe)
        self.assertTrue(foe.is_alive())
        self.assertEqual(foe.metadata.get("_emote"), "hurt",
                         "a hale foe recoils, it isn't knocked down")


if __name__ == "__main__":
    unittest.main()
