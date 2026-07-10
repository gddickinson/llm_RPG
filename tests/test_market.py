"""Market tests (P8.5) — tâtonnement price discovery."""

import unittest

from engine.game_engine import GameEngine
from engine.market import CLAMP_HI, CLAMP_LO, category_of
from items.item_registry import create_item


class TestMarket(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.market = self.engine.market

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_categories(self):
        self.assertEqual(category_of(create_item("sword")), "arms")
        self.assertEqual(category_of(create_item("potion")),
                         "provisions")

    def test_buying_raises_prices(self):
        sword = create_item("sword")
        for _ in range(5):
            self.market.note_purchase(sword)
        self.market.run_day()
        self.assertGreater(self.market.index["arms"], 1.0)

    def test_selling_lowers_prices(self):
        sword = create_item("sword")
        for _ in range(5):
            self.market.note_sale(sword)
        self.market.run_day()
        self.assertLess(self.market.index["arms"], 1.0)

    def test_quiet_days_drift_home(self):
        self.market.index["arms"] = 1.4
        for _ in range(30):
            self.market.run_day()
        self.assertAlmostEqual(self.market.index["arms"], 1.0,
                               delta=0.05)

    def test_clamped(self):
        sword = create_item("sword")
        for _ in range(200):
            for _ in range(9):
                self.market.note_purchase(sword)
            self.market.run_day()
        self.assertLessEqual(self.market.index["arms"], CLAMP_HI)
        for _ in range(400):
            for _ in range(9):
                self.market.note_sale(sword)
            self.market.run_day()
        self.assertGreaterEqual(self.market.index["arms"], CLAMP_LO)

    def test_shop_prices_track_the_index(self):
        merchant = next(n for n in
                        self.engine.npc_manager.npcs.values()
                        if getattr(n.character_class, "value", "") ==
                        "merchant")
        sword = create_item("sword")
        sm = self.engine.shop_manager
        base_buy = sm.buy_price(self.engine.player, sword, merchant)
        base_sell = sm.sell_price(self.engine.player, sword, merchant)
        self.market.index["arms"] = 1.5
        self.assertGreater(
            sm.buy_price(self.engine.player, sword, merchant),
            base_buy)
        self.assertGreater(
            sm.sell_price(self.engine.player, sword, merchant),
            base_sell, "sell price must move too — no arbitrage")

    def test_hungry_village_raises_provision_prices(self):
        self.engine.faction_ticker.state["villagers"]["stores"] = 10
        self.market.run_day()
        self.assertGreater(self.market.index["provisions"], 1.0)

    def test_big_moves_hit_the_rumor_mill(self):
        sword = create_item("sword")
        for _ in range(6):
            for _ in range(9):
                self.market.note_purchase(sword)
            self.market.run_day()
            if self.market.index["arms"] >= 1.25:
                break
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("Prices for arms climb", log)

    def test_index_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.market.index["arcana"] = 1.33
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="mkt")
            self.market.index["arcana"] = 1.0
            self.assertTrue(sm.load(self.engine, name="mkt"))
            self.assertAlmostEqual(
                self.engine.market.index["arcana"], 1.33)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
