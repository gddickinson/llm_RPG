"""Tests for gathering nodes — mining / woodcutting / fishing (P2.2)."""

import unittest

from engine.game_engine import GameEngine
from engine.skill_progression import get_skill_xp, add_skill_xp
from items.item_registry import create_item
from world.world_map import TerrainType


def _find_tile(wmap, terrain):
    for y in range(wmap.height):
        for x in range(wmap.width):
            if wmap.get_terrain_at(x, y) == terrain:
                return (x, y)
    return None


class TestGathering(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.gm = self.engine.gathering_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _stand_on(self, terrain):
        pos = _find_tile(self.engine.world.map, terrain)
        if pos is None:
            self.skipTest(f"no {terrain} tile in world")
        self.player.position = pos
        return pos

    def test_mining_requires_pickaxe(self):
        self._stand_on(TerrainType.MOUNTAIN)
        msg = self.engine.forage()
        self.assertIn("pickaxe", msg.lower())
        self.assertEqual(get_skill_xp(self.player, "mining"), 0)

    def test_mining_with_pickaxe_grants_ore_and_xp(self):
        self._stand_on(TerrainType.MOUNTAIN)
        self.player.inventory.append(create_item("pickaxe"))
        msg = self.engine.forage()
        self.assertIn("mine", msg.lower())
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("copper_ore", ids,
                      "level-1 miner should only get copper")
        self.assertGreater(get_skill_xp(self.player, "mining"), 0)

    def test_level_gates_higher_tiers(self):
        self._stand_on(TerrainType.MOUNTAIN)
        self.player.inventory.append(create_item("pickaxe"))
        # Level 1: only copper is unlocked
        skill_id, spec, _ = self.gm.node_at(*self.player.position)
        tiers = self.gm._unlocked_tiers("mining", spec)
        self.assertEqual([t["item"] for t in tiers], ["copper_ore"])
        # Level 35+: all four tiers
        add_skill_xp(self.player, "mining", 10**7)
        tiers = self.gm._unlocked_tiers("mining", spec)
        self.assertEqual(len(tiers), 4)

    def test_node_cooldown(self):
        pos = self._stand_on(TerrainType.MOUNTAIN)
        self.player.inventory.append(create_item("pickaxe"))
        first = self.engine.forage()
        self.assertIn("mine", first.lower())
        second = self.engine.forage()
        self.assertIn("picked clean", second.lower())

    def test_fishing_adjacent_to_water(self):
        # a shoreline tile that genuinely resolves to a FISHING node — a
        # water-adjacent tile touching a mountain/forest resolves to
        # mining/woodcutting first (node_at checks in that order), which
        # a fishing rod can't work, so pin the fishing node directly.
        gm = self.engine.gathering_manager
        wmap = self.engine.world.map
        spot = None
        for y in range(1, wmap.height - 1):
            for x in range(1, wmap.width - 1):
                node = gm.node_at(x, y)
                if wmap.get_terrain_at(x, y) != TerrainType.WATER and \
                        node is not None and node[0] == "fishing":
                    spot = (x, y)
                    break
            if spot:
                break
        if spot is None:
            self.skipTest("no fishing shoreline found")
        self.player.position = spot
        self.player.inventory.append(create_item("fishing_rod"))
        msg = self.engine.forage()
        self.assertIn("fish", msg.lower())
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("raw_trout", ids)

    def test_axe_tool_matching(self):
        from world.gathering import has_tool
        self.assertFalse(has_tool(self.player, "axe"))
        self.player.inventory.append(create_item("crude_axe"))
        self.assertTrue(has_tool(self.player, "axe"))
        self.assertFalse(has_tool(self.player, "pickaxe"),
                         "an axe is not a pickaxe")

    def test_cooking_recipe_trains_cooking(self):
        self.player.inventory.append(create_item("raw_trout"))
        self.engine.craft("cooked_trout")
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("cooked_trout", ids)
        self.assertGreater(get_skill_xp(self.player, "cooking"), 0)

    def test_smelting_trains_smithing(self):
        from items.crafting import craft, find_recipe
        self.player.gold = 20
        self.player.inventory.append(create_item("copper_ore", quantity=2))
        msg = craft(self.player, "bronze_bar", {"forge": True})
        self.assertIn("craft", msg.lower())
        self.engine._award_craft_xp(find_recipe("bronze_bar"))
        self.assertGreater(get_skill_xp(self.player, "smithing"), 0)

    def test_cooldowns_persist_through_save(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.gm.harvested_at[("mining", 3, 3)] = 777
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="g")
            self.gm.harvested_at = {}
            self.assertTrue(sm.load(self.engine, name="g"))
            self.assertEqual(
                self.engine.gathering_manager.harvested_at.get(
                    ("mining", 3, 3)), 777)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
