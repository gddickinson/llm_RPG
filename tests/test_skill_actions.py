"""Skill action tests (P12.8): trip, demoralize, feint, medicine."""

import random
import unittest

from characters.status_effects import effect_value, has_effect
from engine.game_engine import GameEngine
from engine.skill_actions import (battle_medicine, demoralize, feint,
                                  trip)
from items.item_registry import create_item
from world.monsters import build_monster
from world.world_map import TerrainType


class _Rng:
    def __init__(self, roll=10, rand=0.5):
        self.roll = roll
        self.rand = rand

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def random(self):
        return self.rand


class TestSkillActions(unittest.TestCase):
    def setUp(self):
        # seed the global RNG so worldgen + the built wolf's stats are stable
        # regardless of how many tests ran before (adding test files elsewhere
        # shifts the shared seed and used to tip the feint check — the known
        # RNG-pollution flake). A per-test seed makes this suite reproducible.
        random.seed(0x5C111)
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 10, self.wmap.height - 8
        for y in range(self.oy - 2, self.oy + 3):
            for x in range(self.ox - 2, self.ox + 4):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _foe(self, dx=1, dy=0):
        foe = build_monster("wolf", (self.ox + dx, self.oy + dy))
        foe.hp = foe.max_hp = 99
        self.engine.npc_manager.add_npc(foe)
        self.wmap.place_character(foe, *foe.position)
        return foe

    def test_trip_drops_them_or_you(self):
        foe = self._foe()
        self.engine.combat_system.rng = _Rng(roll=18)
        trip(self.engine)
        self.assertTrue(has_effect(foe, "prone"),
                        "a made trip is a takedown")
        from characters.status_effects import remove_effect
        remove_effect(foe, "prone")
        self.engine.combat_system.rng = _Rng(roll=1)
        trip(self.engine)
        self.assertTrue(has_effect(self.player, "prone"),
                        "a fumbled trip drops YOU")

    def test_demoralize_frightens_with_degrees(self):
        foe = self._foe(dx=3)      # voice range, not melee
        # demoralize runs an internal advance_turn (the whole world sim); clear
        # every OTHER NPC so that turn can't incidentally act on our foe and
        # drop the effect (the flake) — the 99-HP foe can't die on its own
        for nid in list(self.engine.npc_manager.npcs):
            if nid != foe.id:
                other = self.engine.npc_manager.npcs[nid]
                self.wmap.remove_character(other)
                self.engine.npc_manager.remove_npc(nid)
        self.engine.combat_system.rng = _Rng(roll=20)
        msg = demoralize(self.engine)
        self.assertIn("Frightened 2", msg, "a crit roar hits harder")
        # a crit roar (Frightened 2) survives its own turn's single decay tick
        self.assertTrue(has_effect(foe, "frightened"),
                        "the roar leaves them shaken")

    def test_demoralize_immunity_is_the_anti_spam(self):
        foe = self._foe()
        self.engine.combat_system.rng = _Rng(roll=2)   # fails
        demoralize(self.engine)
        msg = demoralize(self.engine)
        self.assertIn("heard your threats", msg,
                      "even a failed attempt spends the words")
        self.engine.world.advance_time(11)
        self.engine.combat_system.rng = _Rng(roll=15)
        msg = demoralize(self.engine)
        self.assertIn("Frightened", msg,
                      "the immunity expires with time")

    def test_feint_opens_them_up(self):
        foe = self._foe()
        self.engine.combat_system.rng = _Rng(roll=15)
        feint(self.engine)
        self.assertTrue(has_effect(foe, "off_guard"),
                        "a read feint leaves them open")

    def test_feint_crit_fail_opens_you_up(self):
        self._foe()
        self.engine.combat_system.rng = _Rng(roll=1)
        feint(self.engine)
        self.assertTrue(has_effect(self.player, "off_guard"))

    def test_battle_medicine_needs_a_bandage(self):
        self.player.inventory = []
        msg = battle_medicine(self.engine)
        self.assertIn("bandage", msg.lower())

    def test_battle_medicine_heals_once_a_day(self):
        self.player.inventory = [create_item("bandage"),
                                 create_item("bandage")]
        self.player.hp = 5
        self.engine.combat_system.rng = _Rng(roll=15)
        battle_medicine(self.engine)
        self.assertEqual(self.player.hp, 13, "+8 on a plain success")
        self.assertEqual(len(self.player.inventory), 1,
                         "the bandage burned")
        msg = battle_medicine(self.engine)
        self.assertIn("once today", msg)
        self.assertEqual(len(self.player.inventory), 1,
                         "no bandage wasted on a refusal")

    def test_battle_medicine_saves_the_bandage_when_whole(self):
        """PT4 finding: full HP + no infection = nothing to treat."""
        self.player.inventory = [create_item("bandage")]
        self.player.hp = self.player.max_hp
        self.player.metadata["infection"] = None
        msg = battle_medicine(self.engine)
        self.assertIn("save the bandage", msg)
        self.assertEqual(len(self.player.inventory), 1,
                         "nothing burned")
        self.assertNotIn("battle_med_day", self.player.metadata,
                         "the daily immunity is not spent either")

    def test_battle_medicine_crit_fail_hurts(self):
        self.player.inventory = [create_item("bandage")]
        self.player.hp = 10
        self.engine.combat_system.rng = _Rng(roll=1)
        battle_medicine(self.engine)
        self.assertEqual(self.player.hp, 8, "slipped hands cut")


if __name__ == "__main__":
    unittest.main()