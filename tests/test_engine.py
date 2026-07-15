"""End-to-end engine smoke tests."""

import unittest

from engine.game_engine import GameEngine


class TestEngineSmoke(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_player_exists(self):
        self.assertIsNotNone(self.engine.player)
        self.assertEqual(self.engine.player.id, "player")

    def test_npcs_loaded(self):
        names = [n.name for n in self.engine.npc_manager.npcs.values()]
        self.assertIn("Goren", names)
        self.assertIn("Gorkash", names)

    def test_world_generated(self):
        self.assertGreater(len(self.engine.world.locations), 3)

    def test_quests_offered(self):
        if not self.engine.quest_manager:
            self.skipTest("quest system disabled")
        # New flow: quests are offered (AVAILABLE), not active until accepted
        self.assertGreaterEqual(
            len(self.engine.quest_manager.available()), 1)

    def test_move_advances_turn(self):
        t = self.engine.turn_counter
        ok = self.engine.move_player(0, 1)
        # Either moved or didn't, either way turn advances if move succeeded
        if ok:
            self.assertGreater(self.engine.turn_counter, t)

    def test_game_state_shape(self):
        s = self.engine.get_game_state()
        for key in ("player", "map", "world", "npcs",
                    "visible_map", "location",
                    "time_of_day", "formatted_time",
                    "recent_events", "turn", "quests", "xp"):
            self.assertIn(key, s)

    def test_pickup_and_drop(self):
        from items.item_registry import create_item
        item = create_item("potion")
        x, y = self.engine.player.position
        self.engine.world.add_item_to_ground(item, x, y)
        # count UNITS: a potion may merge into a starting potion stack (P25.1)
        units = lambda: sum(getattr(it, "quantity", 1)
                            for it in self.engine.player.inventory)
        before = units()
        msg = self.engine.pickup_item()
        self.assertIn("pick up", msg.lower())
        self.assertEqual(units(), before + 1)
        drop_msg = self.engine.drop_item("Healing Potion")
        self.assertIn("drop", drop_msg.lower())

    def test_use_potion_heals(self):
        from items.item_registry import create_item
        self.engine.player.hp = 5
        self.engine.player.inventory.append(create_item("potion"))
        msg = self.engine.use_item("potion")
        self.assertGreater(self.engine.player.hp, 5)


if __name__ == "__main__":
    unittest.main()
