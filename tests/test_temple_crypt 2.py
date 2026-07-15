"""Temple + crypt tests (P9.3)."""

import unittest

from engine.game_engine import GameEngine


class TestTempleCrypt(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _sanctuary(self):
        return self.engine.interiors["Temple of Light"]

    def test_sanctuary_over_crypt(self):
        sanctuary = self._sanctuary()
        self.assertTrue(sanctuary.ground)
        crypt = sanctuary.level_below
        self.assertIsNotNone(crypt)
        self.assertTrue(crypt.dark)
        self.assertEqual(sanctuary.stairs_down, crypt.stairs_up)

    def test_altar_prayer_still_works_inside(self):
        from engine.furniture import interact
        sanctuary = self._sanctuary()
        self.engine.current_interior = sanctuary
        altar = next(f for f in sanctuary.furniture
                     if f["name"] == "Altar")
        self.engine.player.position = (altar["x"], altar["y"])
        msg = interact(self.engine)
        self.assertTrue("pray" in msg.lower() or
                        "answers" in msg.lower(), msg)
        self.engine.current_interior = None

    def test_banking_works_in_the_sanctuary(self):
        sanctuary = self._sanctuary()
        self.engine.current_interior = sanctuary
        self.engine.player.gold = 40
        msg = self.engine.deposit_gold(20)
        self.assertIn("deposit", msg.lower())
        self.engine.current_interior = None

    def test_the_dead_sleep_restlessly_below(self):
        crypt = self._sanctuary().level_below
        spawned = self.engine.structures.on_enter_level(crypt)
        self.assertEqual(spawned, 2)
        natives = [n for n in self.engine.npc_manager.npcs.values()
                   if n.metadata.get("zone") == crypt.name]
        self.assertTrue(all(n.name == "Restless Bones"
                            for n in natives))

    def test_blessed_rewards_in_the_crypt_chest(self):
        crypt = self._sanctuary().level_below
        chest = next(f for f in crypt.furniture
                     if f["name"] == "Chest")
        key = f"temple_crypt:{chest['x']}:{chest['y']}"
        contents = self.engine.structures.chest_contents.get(key, [])
        ids = [getattr(i, "id", "") for i in contents]
        self.assertIn("scroll_heal", ids)
        self.assertIn("amulet_health", ids)


if __name__ == "__main__":
    unittest.main()
