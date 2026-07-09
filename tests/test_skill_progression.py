"""Tests for the skill progression lattice (P2.1)."""

import unittest

from engine.game_engine import GameEngine
from engine.skill_progression import (
    SKILLS, all_skill_ids, xp_for_level_up, total_xp_for_level,
    level_for_xp, progress_within_level, add_skill_xp, get_skill_level,
    get_skill_xp, total_skill_level, MAX_LEVEL, BASE_XP, GROWTH,
)


class TestCurve(unittest.TestCase):
    def test_eight_skills_defined(self):
        self.assertGreaterEqual(len(SKILLS), 8)
        self.assertIn("mining", SKILLS)
        self.assertIn("agility", SKILLS)

    def test_curve_is_geometric(self):
        self.assertEqual(xp_for_level_up(1), BASE_XP)
        # Each level costs ~GROWTH x the previous
        for lv in range(2, 40):
            ratio = xp_for_level_up(lv + 1) / xp_for_level_up(lv)
            self.assertAlmostEqual(ratio, GROWTH, delta=0.02)

    def test_early_levels_fast_late_levels_slow(self):
        # OSRS property: the last ~7 levels cost about as much as
        # everything before them
        to_43 = total_xp_for_level(43)
        to_50 = total_xp_for_level(50)
        self.assertGreater(to_50 - to_43, to_43 * 0.8)

    def test_level_for_xp_roundtrip(self):
        for lv in (1, 2, 10, 25, 49, 50):
            self.assertEqual(level_for_xp(total_xp_for_level(lv)), lv)
            if lv > 1:
                self.assertEqual(
                    level_for_xp(total_xp_for_level(lv) - 1), lv - 1)

    def test_level_caps_at_max(self):
        self.assertEqual(level_for_xp(10**9), MAX_LEVEL)
        self.assertEqual(progress_within_level(10**9), (0, 0))


class TestAwarding(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_add_xp_and_level_up_message(self):
        msgs = add_skill_xp(self.player, "mining", BASE_XP)
        self.assertEqual(get_skill_level(self.player, "mining"), 2)
        self.assertTrue(any("Mining level up" in m for m in msgs))

    def test_unknown_skill_ignored(self):
        self.assertEqual(add_skill_xp(self.player, "basket_weaving", 50), [])

    def test_forage_grants_foraging_xp(self):
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.get_terrain_at(x, y) == TerrainType.FOREST:
                    self.player.position = (x, y)
                    before = get_skill_xp(self.player, "foraging")
                    self.engine.forage()
                    self.assertGreater(
                        get_skill_xp(self.player, "foraging"), before)
                    return
        self.skipTest("no forest tile")

    def test_craft_grants_alchemy_xp(self):
        from items.item_registry import create_item
        self.player.inventory.append(create_item("herb_bundle"))
        self.player.gold = 50
        self.engine.craft("potion")
        self.assertGreater(get_skill_xp(self.player, "alchemy"), 0)
        self.assertEqual(get_skill_xp(self.player, "smithing"), 0)

    def test_forge_craft_grants_smithing_xp(self):
        from items.item_registry import create_item
        from items.crafting import craft
        self.player.gold = 100
        self.player.inventory.append(create_item("iron_bar", quantity=2))
        # Craft directly with forge props, then award through engine path
        loc_props = {"forge": True}
        msg = craft(self.player, "sword", loc_props)
        self.assertIn("craft", msg.lower())
        self.engine._award_craft_xp(
            __import__("items.crafting", fromlist=["find_recipe"])
            .find_recipe("sword"))
        self.assertGreater(get_skill_xp(self.player, "smithing"), 0)

    def test_skills_persist_through_save(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        add_skill_xp(self.player, "mining", 500)
        level = get_skill_level(self.player, "mining")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="sk")
            self.player.metadata["skills"] = {}
            self.assertTrue(sm.load(self.engine, name="sk"))
            self.assertEqual(
                get_skill_level(self.engine.player, "mining"), level)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_total_skill_level(self):
        base = total_skill_level(self.player)
        add_skill_xp(self.player, "mining", BASE_XP)
        self.assertEqual(total_skill_level(self.player), base + 1)


if __name__ == "__main__":
    unittest.main()
