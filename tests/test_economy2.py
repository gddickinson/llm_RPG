"""Economy II tests (P12.10): elasticity, regions, haggling."""

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


class _Rng:
    def __init__(self, roll=10, rand=0.5):
        self.roll = roll
        self.rand = rand

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def random(self):
        return self.rand


class TestEconomy2(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.sm = self.engine.shop_manager
        self.merchant = next(
            n for n in self.engine.npc_manager.npcs.values()
            if n.is_active() and
            getattr(n.character_class, "value", "") == "merchant")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_buying_out_the_stock_raises_the_price(self):
        cat = self.sm.catalog_for(self.merchant)
        target = next(it for it in cat.items)
        item_id = target.id
        base_mult = self.sm.stock_multiplier(self.merchant, item_id)
        # the player buys them all out
        cat.items = [it for it in cat.items if it.id != item_id]
        drained = self.sm.stock_multiplier(self.merchant, item_id)
        self.assertGreater(drained, base_mult,
                           "scarcity raises the price")

    def test_flooding_the_shop_tanks_the_price(self):
        cat = self.sm.catalog_for(self.merchant)
        for _ in range(10):
            cat.items.append(create_item("ale"))
        glut = self.sm.stock_multiplier(self.merchant, "ale")
        self.assertLess(glut, 1.0, "a glut pays less")
        self.assertGreaterEqual(glut, 0.5, "clamped at the floor")

    def test_restock_self_heals(self):
        cat = self.sm.catalog_for(self.merchant)
        item_id = cat.items[0].id
        cat.items = []
        self.engine.world.time += 24 * 60 + 1
        self.sm.refresh_all_if_due()
        healed = self.sm.stock_multiplier(self.merchant, item_id)
        self.assertAlmostEqual(healed, 1.0, delta=0.01,
                               msg="the daily restock heals prices")

    def test_regional_arbitrage_exists(self):
        """Provisions: cheap in Riverside (0.8), dear in
        Stonepine (1.3) — buy low, carry, sell high."""
        bread = create_item("bread")

        class _Fake:
            def __init__(self, pos):
                self.position = pos

        riverside = next(l for l in self.engine.world.locations
                         if "Riverside" in l.name)
        stonepine = next((l for l in self.engine.world.locations
                          if "Stonepine" in l.name), None)
        if stonepine is None:
            self.skipTest("no Stonepine on this map")
        r_mult = self.sm.regional_multiplier(
            _Fake((riverside.x, riverside.y)), bread)
        s_mult = self.sm.regional_multiplier(
            _Fake((stonepine.x, stonepine.y)), bread)
        self.assertLess(r_mult, s_mult,
                        "the river feeds; the camp pays")

    def test_haggle_success_earns_a_deal(self):
        self.engine.combat_system.rng = _Rng(roll=15)
        self.sm.haggle(self.player, self.merchant)
        state = self.sm.haggle_state(self.player, self.merchant)
        self.assertEqual(state["discount"], 0.05)
        ale = create_item("ale")
        with_deal = self.sm.buy_price(self.player, ale,
                                      self.merchant)
        self.player.metadata["haggle_deal"] = {}
        without = self.sm.buy_price(self.player, ale, self.merchant)
        self.assertLessEqual(with_deal, without,
                             "the earned deal shows at the till")

    def test_patience_is_finite(self):
        self.engine.combat_system.rng = _Rng(roll=5)   # plain fails
        for _ in range(3):
            self.sm.haggle(self.player, self.merchant)
        state = self.sm.haggle_state(self.player, self.merchant)
        self.assertEqual(state["patience"], 0)
        msg = self.sm.haggle(self.player, self.merchant)
        self.assertIn("done haggling", msg)

    def test_insulting_the_merchant_costs_reputation(self):
        rel0 = self.merchant.get_relationship(self.player.id)
        self.engine.combat_system.rng = _Rng(roll=1)   # crit fail
        msg = self.sm.haggle(self.player, self.merchant)
        self.assertIn("Buy it or leave", msg)
        self.assertLess(self.merchant.get_relationship(self.player.id),
                        rel0, "failed haggles cost standing")
        state = self.sm.haggle_state(self.player, self.merchant)
        self.assertEqual(state["patience"], 0)

    def test_patience_resets_with_the_day(self):
        self.engine.combat_system.rng = _Rng(roll=1)
        self.sm.haggle(self.player, self.merchant)
        self.engine.world.time += 24 * 60 + 1
        state = self.sm.haggle_state(self.player, self.merchant)
        self.assertEqual(state["patience"], 3,
                         "a new day, a fresh temper")


if __name__ == "__main__":
    unittest.main()
