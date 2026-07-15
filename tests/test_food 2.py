"""Food economy tests (P12.5): tempo, freshness, brews, combos."""

import unittest

from characters.status_effects import has_effect
from engine.food import (EAT_DELAY, FRESH_START, attack_gate, chewing,
                         decay_inventory, freshness_of,
                         refresh_rations)
from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.monsters import build_monster
from world.world_map import TerrainType


class _Rng:
    def __init__(self, rand=0.5, roll=10):
        self.rand = rand
        self.roll = roll

    def random(self):
        return self.rand

    def randint(self, a, b):
        return self.roll


class TestFood(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.player.metadata.update({"hunger": 50, "thirst": 10})
        self.ox, self.oy = self.wmap.width - 10, self.wmap.height - 8
        for y in range(self.oy - 2, self.oy + 3):
            for x in range(self.ox - 2, self.ox + 4):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _eat(self, item_id):
        self.player.inventory.append(create_item(item_id))
        return self.engine.player_actions.use(
            create_item(item_id).name)

    def test_eating_costs_tempo(self):
        self.player.hp = 5
        self._eat("bread")
        self.assertGreater(chewing(self.engine), 0)
        wolf = build_monster("wolf", (self.ox + 1, self.oy))
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)
        msg = self.engine.player_actions.attack("Wolf")
        self.assertIn("swallowing", msg)
        self.assertEqual(wolf.hp, wolf.max_hp, "no strike lands")
        for _ in range(EAT_DELAY):
            self.engine.advance_turn()
        self.assertEqual(attack_gate(self.engine), "",
                         "the delay passes")

    def test_combo_food_breaks_no_stride(self):
        self.player.hp = 5
        self._eat("bread")                    # delay is up
        msg = self._eat("meat_pie")           # combo eats through it
        self.assertIn("break stride", msg)
        # and the pie itself set no delay beyond bread's
        self.player.metadata.pop("ate_turn", None)
        msg = self._eat("meat_pie")
        self.assertEqual(chewing(self.engine), 0,
                         "combo food never costs tempo")

    def test_brew_overheals_and_dulls(self):
        self.player.hp = self.player.max_hp
        msg = self._eat("hearty_brew")
        self.assertGreater(self.player.hp, self.player.max_hp,
                           "the brew heals past the limit")
        self.assertTrue(has_effect(self.player, "cursed"),
                        "the sword arm pays for it")

    def test_freshness_decays_and_hearth_restores(self):
        bread = create_item("bread")
        self.player.inventory.append(bread)
        self.assertEqual(freshness_of(bread), FRESH_START)
        decay_inventory(self.engine)
        decay_inventory(self.engine)
        self.assertEqual(freshness_of(bread), FRESH_START - 30)
        refreshed = refresh_rations(self.engine)
        self.assertEqual(refreshed, 1)
        self.assertEqual(freshness_of(bread), FRESH_START)

    def test_stale_food_heals_half_and_can_poison(self):
        bread = create_item("bread")
        bread.use_effect["freshness"] = 10
        self.player.inventory.append(bread)
        self.player.hp = 5
        self.engine.combat_system.rng = _Rng(rand=0.1)  # under risk
        self.engine.player_actions.use("Bread")
        self.assertEqual(self.player.hp, 6,
                         "half heal (+2), then the poison bites (-1)")
        self.assertTrue(has_effect(self.player, "poisoned"),
                        "rotten food bites back")

    def test_fresh_food_is_safe(self):
        self.player.hp = 5
        self.engine.combat_system.rng = _Rng(rand=0.0)
        self._eat("bread")
        self.assertFalse(has_effect(self.player, "poisoned"))
        self.assertEqual(self.player.hp, 9, "full heal when fresh")

    def test_potions_skip_the_chew_delay(self):
        self.player.hp = 5
        self.player.inventory.append(create_item("potion"))
        self.engine.player_actions.use("Healing Potion")
        self.assertEqual(chewing(self.engine), 0,
                         "potions are not food")


if __name__ == "__main__":
    unittest.main()
