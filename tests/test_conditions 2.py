"""Valued condition tests (P12.2): frightened N, persistent damage,
prone, blinded, off-guard."""

import random
import unittest

from characters.status_effects import (ac_penalty, apply_effect,
                                       attack_penalty, check_penalty,
                                       effect_value, has_effect,
                                       tick_effects)
from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType


class _FixedRng:
    def __init__(self, value):
        self.value = value

    def randint(self, a, b):
        return self.value


class _Dummy:
    def __init__(self):
        self.name = "Dummy"
        self.metadata = {}
        self.hp = 30
        self.dexterity = 10
        self.level = 1

    def take_damage(self, n):
        self.hp -= n

    def is_alive(self):
        return self.hp > 0


class TestValuedConditions(unittest.TestCase):
    def test_frightened_decays_and_penalizes(self):
        d = _Dummy()
        apply_effect(d, "frightened", duration=99, value=2)
        self.assertEqual(check_penalty(d), -2)
        self.assertEqual(attack_penalty(d), -2)
        tick_effects(d, rng=random.Random(0))
        self.assertEqual(effect_value(d, "frightened"), 1,
                         "fear fades one step per turn")
        tick_effects(d, rng=random.Random(0))
        self.assertFalse(has_effect(d, "frightened"),
                         "Frightened 0 is gone, duration ignored")

    def test_frightened_bites_every_check(self):
        from engine.skills import Skill, roll_check
        d = _Dummy()
        base = roll_check(d, Skill.LOCKPICKING, dc=10,
                          rng=_FixedRng(10))[1]
        apply_effect(d, "frightened", duration=99, value=2)
        feared = roll_check(d, Skill.LOCKPICKING, dc=10,
                            rng=_FixedRng(10))[1]
        self.assertEqual(base - feared, 2)

    def test_persistent_damage_until_the_flat_check(self):
        d = _Dummy()
        apply_effect(d, "persistent_damage", duration=99,
                     data={"amount": 2, "kind": "bleeding"})
        tick_effects(d, rng=_FixedRng(1))     # flat check fails
        self.assertEqual(d.hp, 28)
        self.assertTrue(has_effect(d, "persistent_damage"))
        events = tick_effects(d, rng=_FixedRng(20))  # check succeeds
        self.assertEqual(d.hp, 26, "it still hurts the turn it ends")
        self.assertFalse(has_effect(d, "persistent_damage"))
        self.assertTrue(any("stops" in e for e in events))

    def test_prone_and_off_guard_penalties(self):
        d = _Dummy()
        apply_effect(d, "prone", duration=3)
        self.assertEqual(ac_penalty(d), -2)
        self.assertEqual(attack_penalty(d), -2)
        apply_effect(d, "off_guard", duration=1)
        self.assertEqual(ac_penalty(d), -4)


class TestConditionsInPlay(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 12, self.wmap.height - 10
        for y in range(self.oy - 3, self.oy + 4):
            for x in range(self.ox - 3, self.ox + 6):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _stage_fight(self):
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)
        foe = build_monster("wolf", (self.ox + 1, self.oy))
        foe.hp = foe.max_hp = 99
        self.engine.npc_manager.add_npc(foe)
        self.wmap.place_character(foe, *foe.position)
        return foe

    def test_flanked_defenders_are_off_guard(self):
        foe = self._stage_fight()
        ally = build_monster("wolf", (self.ox + 2, self.oy))
        ally.hp = ally.max_hp = 99
        self.engine.npc_manager.add_npc(ally)
        self.wmap.place_character(ally, *ally.position)
        self.engine.companion_manager.members = lambda: [ally]
        self.engine.combat_system.rng = _FixedRng(10)
        self.engine.combat_system._resolve(self.player, foe)
        self.assertTrue(has_effect(foe, "off_guard"),
                        "flanking makes the target off-guard now")

    def test_natural_crit_opens_a_wound(self):
        foe = self._stage_fight()
        self.engine.combat_system.rng = _FixedRng(20)
        self.engine.combat_system._resolve(self.player, foe)
        self.assertTrue(has_effect(foe, "persistent_damage"),
                        "a perfect strike bleeds")

    def test_prone_npcs_spend_the_action_standing(self):
        foe = self._stage_fight()
        apply_effect(foe, "prone", duration=3)
        router = self.engine.action_router
        acted = router.process(foe, {"action": "wait"})
        self.assertFalse(acted, "standing up costs the turn")
        self.assertFalse(has_effect(foe, "prone"))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("scrambles", log)

    def test_blinded_player_sees_one_tile(self):
        base = self.engine.effective_visibility()
        self.assertGreater(base, 1)
        apply_effect(self.player, "blinded", duration=5)
        self.assertEqual(self.engine.effective_visibility(), 1,
                         "FOV powers blindness")

    def test_crit_shove_knocks_prone(self):
        from engine.tactics import shove

        class _Seq:
            def __init__(self, vals):
                self.vals = list(vals)

            def randint(self, a, b):
                return self.vals.pop(0)

        foe = self._stage_fight()
        # a clear lane to tumble down, and pin the clock off the NPC-AI
        # boundary so the shove's incidental world tick doesn't let the
        # foe scramble straight back to its feet (P12.2) before we look
        for i in range(1, 4):
            ch = self.wmap.get_character_at(self.ox + 1 + i, self.oy)
            if ch is not None:
                self.wmap.remove_character(ch)
        self.engine.turn_counter = 1
        shove(self.engine, rng=_Seq([20, 1]))
        self.assertTrue(has_effect(foe, "prone"),
                        "hurled sprawling means PRONE")

    def test_intimidate_applies_frightened_2(self):
        npc = next(n for n in self.engine.npc_manager.npcs.values()
                   if n.is_active())
        self.engine.persuasion.rng = _FixedRng(20)
        self.engine.persuasion.attempt(npc, "intimidate", "move")
        self.assertEqual(effect_value(npc, "frightened"), 2)


if __name__ == "__main__":
    unittest.main()
