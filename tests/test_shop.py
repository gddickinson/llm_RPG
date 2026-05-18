"""Tests for the shop / merchant system."""

import unittest

from engine.game_engine import GameEngine
from engine.shop import ShopManager, _category_for_npc


class TestShop(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_tavern_keeper_sells_drink(self):
        sm = self.engine.shop_manager
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        cat = sm.catalog_for(goren)
        ids = [it.id for it in cat.items]
        # Tavern category includes ale + bread
        self.assertTrue(any(i in ids for i in ("ale", "bread", "mead")))

    def test_smith_sells_weapons(self):
        sm = self.engine.shop_manager
        durgan = self.engine.npc_manager.get_npc("blacksmith_01")
        cat = sm.catalog_for(durgan)
        ids = [it.id for it in cat.items]
        self.assertTrue(any(i in ids for i in
                            ("sword", "longsword", "battleaxe", "warhammer")))

    def test_buy_price_higher_than_sell(self):
        sm = self.engine.shop_manager
        durgan = self.engine.npc_manager.get_npc("blacksmith_01")
        from items.item_registry import create_item
        sword = create_item("sword")
        buy = sm.buy_price(self.engine.player, sword, durgan)
        sell = sm.sell_price(self.engine.player, sword, durgan)
        self.assertGreater(buy, sell)

    def test_faction_discount(self):
        sm = self.engine.shop_manager
        durgan = self.engine.npc_manager.get_npc("blacksmith_01")
        from items.item_registry import create_item
        from characters.factions import Faction, set_rep
        sword = create_item("sword")
        base_buy = sm.buy_price(self.engine.player, sword, durgan)
        # Boost merchant rep — buy price should drop
        set_rep(self.engine.player, Faction.MERCHANTS, 80)
        better_buy = sm.buy_price(self.engine.player, sword, durgan)
        self.assertLess(better_buy, base_buy)

    def test_merchants_near(self):
        from engine.shop import merchants_near
        # Move player adjacent to Goren
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (goren.position[0] + 1,
                                       goren.position[1])
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        nearby = merchants_near(self.engine, self.engine.player)
        self.assertTrue(any(n.id == "tavernkeeper_01" for n in nearby))


class TestCategoryHeuristics(unittest.TestCase):
    def test_blacksmith_category(self):
        class FakeCls:
            value = "merchant"
        class FakeNPC:
            id = "blacksmith_01"
            name = "Durgan"
            character_class = FakeCls()
            home_location = "Durgan's Forge"
        self.assertEqual(_category_for_npc(FakeNPC()), "blacksmith")


if __name__ == "__main__":
    unittest.main()
