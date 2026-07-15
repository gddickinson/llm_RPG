"""Traversal aid tests (P11.3): gear, blessings, water-walking."""

import unittest

from engine.game_engine import GameEngine
from engine.hazards import water_hazard_tick
from items.item_registry import create_item
from world.world_map import TerrainType


class _FixedRng:
    def __init__(self, value):
        self.value = value

    def randint(self, a, b):
        return self.value

    def choice(self, seq):
        return seq[0]


class TestTraversalAids(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.player = self.engine.player
        self.trav = self.engine.traversal
        self.ox, self.oy = self.wmap.width - 12, self.wmap.height - 10
        for y in range(self.oy - 4, self.oy + 6):
            for x in range(self.ox - 4, self.ox + 8):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        # a known baseline: no stat/skill surprises
        self.player.dexterity = 10
        self.player.strength = 10
        self.player.metadata["skills"] = {}
        self.player.metadata["fatigue"] = 10
        self.player.inventory = []

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put_player(self, x, y):
        self.wmap.remove_character(self.player)
        self.player.position = (x, y)
        self.wmap.place_character(self.player, x, y)

    def _lake(self):
        for dy in range(5):
            for dx in range(5):
                self.wmap.terrain[self.oy + dy][self.ox + dx] = \
                    TerrainType.WATER
        return self.ox + 2, self.oy + 2   # deep center

    def test_rope_turns_a_failed_climb_into_a_made_one(self):
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.MOUNTAIN
        self._put_player(self.ox, self.oy)
        self.trav.rng = _FixedRng(8)     # 8 + lvl1 + 0 = 9 < DC 12
        self.assertIsNotNone(
            self.trav.attempt_cross(self.ox + 1, self.oy))
        self.assertEqual(self.player.position, (self.ox, self.oy),
                         "without rope the roll misses")
        self.player.inventory.append(create_item("rope"))
        self.assertEqual(self.trav.aid_bonus("climb"), 3)
        self.trav.attempt_cross(self.ox + 1, self.oy)
        self.assertEqual(self.player.position,
                         (self.ox + 1, self.oy),
                         "rope makes the same roll succeed")

    def test_climbing_picks_stack_with_rope(self):
        self.player.inventory = [create_item("rope"),
                                 create_item("climbing_picks")]
        self.assertEqual(self.trav.aid_bonus("climb"), 8)

    def test_water_walking_crosses_without_a_check(self):
        x, y = self._lake()
        from characters.status_effects import apply_effect
        apply_effect(self.player, "water_walking", 20)
        self._put_player(self.ox - 1, self.oy + 2)
        self.trav.rng = _FixedRng(1)     # would doom any real check
        for _ in range(3):
            self.trav.attempt_cross(self.player.position[0] + 1,
                                    self.player.position[1])
        self.assertEqual(self.player.position[0], self.ox + 2,
                         "the surface bears you")
        hp0 = self.player.hp
        self.player.metadata["breath"] = 0
        water_hazard_tick(self.engine)
        self.assertEqual(self.player.hp, hp0,
                         "no struggle while water-walking")

    def test_swimmers_grace_helps_the_struggle(self):
        x, y = self._lake()
        self._put_player(x, y)
        self.trav.rng = _FixedRng(6)     # 6 + 1 + 0 = 7 < DC 12
        hp0 = self.player.hp
        self.player.metadata["breath"] = 0
        water_hazard_tick(self.engine)
        self.assertLess(self.player.hp, hp0, "graceless, you sink")
        self.player.hp = hp0
        self.player.metadata.pop("drown_turns", None)
        from characters.status_effects import apply_effect
        apply_effect(self.player, "swimmers_grace", 20)
        self.player.metadata["breath"] = 0
        water_hazard_tick(self.engine)   # 7 + 5 = 12 >= DC 12
        self.assertEqual(self.player.hp, hp0,
                         "the blessing keeps your head up")

    def test_water_walk_spell_self_casts(self):
        self.player.metadata["spells_known"] = ["water_walk"]
        self.player.metadata["mana"] = 20
        self.player.metadata["max_mana"] = 20
        self.engine.cast_spell("water_walk")
        from characters.status_effects import has_effect
        self.assertTrue(has_effect(self.player, "water_walking"))

    def test_heavy_pack_telegraphs_drop_or_sink(self):
        x, y = self._lake()
        self._put_player(x, y)
        from engine.carry import capacity
        self.player.inventory = [create_item("bread")
                                 for _ in range(capacity(self.player))]
        self.trav.rng = _FixedRng(2)
        self.player.hp = self.player.max_hp
        self.player.metadata["breath"] = 0
        water_hazard_tick(self.engine)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("drop something", log.lower())

    def test_aid_content_is_data(self):
        rope = create_item("rope")
        self.assertEqual(rope.equip_bonuses.get("climb"), 3)
        scroll = create_item("scroll_water_walk")
        self.assertEqual(scroll.use_effect.get("spell"), "water_walk")
        from engine.spells import SPELL_REGISTRY
        self.assertIn("water_walk", SPELL_REGISTRY)
        self.assertIn("swimmers_grace", SPELL_REGISTRY)


if __name__ == "__main__":
    unittest.main()
