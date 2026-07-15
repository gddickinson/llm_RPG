"""Regional achievement diary tests (P2.7)."""

import unittest

from engine.game_engine import GameEngine
from engine.diaries import DIARIES


def _complete_tier(engine, region, tier):
    """Force-satisfy every task in a tier via the underlying trackers."""
    from engine.skill_progression import add_skill_xp, total_xp_for_level
    coll = engine.player.metadata.setdefault("collection", {})
    for cat in ("items", "kills", "crafts", "places"):
        coll.setdefault(cat, [])
    for task in DIARIES[region]["tiers"][tier]["tasks"]:
        t = task["type"]
        if t == "place":
            coll["places"].append(task["target"])
        elif t == "kill":
            coll["kills"].append(task["target"])
        elif t == "collect":
            coll["items"].append(task["target"])
        elif t == "craft":
            coll["crafts"].append(task["target"])
        elif t == "skill":
            add_skill_xp(engine.player, task["target"],
                         total_xp_for_level(task.get("level", 1)))


class TestDiaries(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.dm = self.engine.diary_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_three_regions_three_tiers(self):
        self.assertEqual(len(DIARIES), 3)
        for spec in DIARIES.values():
            self.assertEqual(set(spec["tiers"]), {"easy", "medium", "hard"})

    def test_progress_starts_incomplete(self):
        done, total = self.dm.tier_progress("oakvale", "hard")
        self.assertLess(done, total)

    def test_completing_tier_auto_claims_with_rewards(self):
        _complete_tier(self.engine, "oakvale", "easy")
        gold_before = self.player.gold
        msgs = self.dm.check_and_claim()
        self.assertTrue(any("easy tier complete" in m for m in msgs), msgs)
        self.assertEqual(self.player.gold, gold_before + 50)
        self.assertIn("easy", self.dm.claimed("oakvale"))
        # No double-claim
        self.assertEqual(self.dm.check_and_claim(), [])

    def test_item_rewards_granted(self):
        _complete_tier(self.engine, "oakvale", "medium")
        self.dm.check_and_claim()
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("potion_might", ids)

    def test_diary_discount_applies_to_regional_merchant(self):
        merchant = self.engine.npc_manager.get_npc("blacksmith_01")  # Durgan
        if merchant is None:
            self.skipTest("Durgan missing")
        from items.item_registry import create_item
        item = create_item("sword")
        base = self.engine.shop_manager.buy_price(
            self.player, item, merchant)
        _complete_tier(self.engine, "oakvale", "easy")
        self.dm.check_and_claim()
        discounted = self.engine.shop_manager.buy_price(
            self.player, item, merchant)
        self.assertLess(discounted, base)

    def test_discount_does_not_leak_to_other_regions(self):
        merchant = self.engine.npc_manager.get_npc("camp_smith_01")  # Hilde
        if merchant is None:
            self.skipTest("Hilde missing")
        _complete_tier(self.engine, "oakvale", "easy")
        self.dm.check_and_claim()
        self.assertEqual(self.dm.discount_for_merchant(merchant), 0.0)

    def test_wired_into_turn_loop(self):
        _complete_tier(self.engine, "stonepine", "easy")
        for _ in range(11):
            self.engine.advance_turn()
        self.assertIn("easy", self.dm.claimed("stonepine"))

    def test_claims_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        _complete_tier(self.engine, "riverside", "easy")
        self.dm.check_and_claim()
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="dia")
            self.player.metadata["diaries"] = {}
            self.assertTrue(sm.load(self.engine, name="dia"))
            self.assertIn(
                "easy",
                self.engine.diary_manager.claimed("riverside"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_overlay_lines_render(self):
        lines = self.dm.overlay_lines()
        self.assertTrue(any("Oakvale Diary" in ln for ln in lines))
        self.assertTrue(any("[ ]" in ln or "[x]" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
