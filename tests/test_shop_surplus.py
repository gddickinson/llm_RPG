"""Shop stock from local produce (P16.2c): a settlement's production
surplus reaches the local merchant's shelves — the goods move from the
store onto the stall, closing the produce -> shop -> player loop."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from engine.shop import SHELF_STOCK


def _has(cat, good):
    return sum(1 for it in cat.items
               if getattr(it, "id", "") == good)


class TestShopSurplus(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.prod = self.engine.production
        setts = self.prod._settlements()
        if not setts:
            self.skipTest("no settlements")
        self.sett = setts[0]
        # a merchant standing in that settlement
        self.merchant = next(
            (n for n in self.engine.npc_manager.npcs.values()
             if getattr(n.character_class, "value", "") in
             ("merchant", "cleric", "wizard", "ranger") and n.is_active()),
            None)
        if self.merchant is None:
            self.skipTest("no merchant-class NPC")
        self.merchant.position = self.sett.center()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _fresh_catalog(self):
        self.engine.shop_manager.catalogs.pop(self.merchant.id, None)
        return self.engine.shop_manager.catalog_for(self.merchant)

    def test_surplus_reaches_the_shelf(self):
        self.prod.store_of(self.sett.name)["logs"] = 10
        cat = self._fresh_catalog()
        self.assertEqual(_has(cat, "logs"), SHELF_STOCK,
                         "a few logs go on sale")

    def test_the_goods_move_off_the_store(self):
        self.prod.store_of(self.sett.name)["logs"] = 10
        self._fresh_catalog()
        self.assertEqual(self.prod.store_of(self.sett.name)["logs"],
                         10 - SHELF_STOCK, "the shelved logs left the larder")

    def test_a_thin_store_gives_what_it_has(self):
        self.prod.store_of(self.sett.name)["logs"] = 2   # < SHELF_STOCK
        cat = self._fresh_catalog()
        self.assertEqual(_has(cat, "logs"), 2)
        self.assertEqual(self.prod.store_of(self.sett.name)["logs"], 0)

    def test_nothing_is_created_moving_to_the_shelf(self):
        self.prod.store_of(self.sett.name)["logs"] = 10
        cat = self._fresh_catalog()
        shelved = _has(cat, "logs")
        left = self.prod.store_of(self.sett.name)["logs"]
        self.assertEqual(shelved + left, 10, "carried onto the shelf, not minted")

    def test_no_surplus_stocks_the_usual_wares(self):
        # clear the settlement's store; the shop still has its base catalog
        self.prod.stores[self.sett.name] = {}
        cat = self._fresh_catalog()
        self.assertGreater(len(cat.items), 0, "the merchant isn't emptied")

    def test_gold_budget_accounts_for_the_produce(self):
        self.prod.store_of(self.sett.name)["logs"] = 12
        cat = self._fresh_catalog()
        self.assertGreater(cat.gold, 100, "budget scales with the fuller stall")


if __name__ == "__main__":
    unittest.main()
