"""Tutorial Island tests (P4.4c)."""

import unittest

from engine.game_engine import GameEngine
from world.tutorial_island import ISLAND_NAME, SPAWN, BOAT_TILE
from items.item_registry import create_item


class TestTutorialIsland(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False,
            start_tutorial=True)
        self.engine.start_game()
        self.player = self.engine.player
        self.tm = self.engine.tutorial_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_starts_on_island_with_rod_and_cast(self):
        self.assertTrue(self.tm.active)
        self.assertEqual(self.engine.current_dungeon.name, ISLAND_NAME)
        self.assertEqual(self.player.position, SPAWN)
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("fishing_rod", ids)
        for nid in ("tut_willem", "tut_bors", "tut_dummy"):
            self.assertIsNotNone(self.engine.npc_manager.get_npc(nid))

    def test_step_sequence(self):
        self.assertIn("Willem", self.tm.current_step())
        # 1) talk
        willem = self.engine.npc_manager.get_npc("tut_willem")
        willem.position = (self.player.position[0] + 1,
                           self.player.position[1])
        self.engine.dialog_system.player_to_npc(willem.id, "Hello!")
        self.assertIn("Fish", self.tm.current_step())
        # 2) fish (simulate the catch reaching the collection log)
        self.player.inventory.append(create_item("raw_trout"))
        self.engine.advance_turn()
        self.assertIn("Cook", self.tm.current_step())
        # 3) cook
        self.engine.craft("cooked_trout")
        self.engine.advance_turn()
        self.assertIn("Eat", self.tm.current_step())
        # 4) eat
        self.player.metadata["hunger"] = 50
        self.engine.use_item("Cooked Trout")
        self.assertIn("dummy", self.tm.current_step())
        # 5) fight (stand adjacent first)
        dummy = self.engine.npc_manager.get_npc("tut_dummy")
        dummy.hp = 1
        self.player.position = (dummy.position[0] + 1,
                                dummy.position[1])
        for _ in range(40):
            self.engine.combat_system.player_attack(dummy.name)
            if not dummy.is_active():
                break
        self.assertFalse(dummy.is_active(), "dummy should be defeated")
        self.assertIn("sail", self.tm.current_step().lower())

    def test_tab_away_from_boat_refuses(self):
        msg = self.tm.try_depart()
        self.assertIn("boat", msg.lower())
        self.assertTrue(self.tm.active, "must not depart off the dock")

    def test_departure_from_boat_tile(self):
        self.player.position = BOAT_TILE
        msg = self.tm.try_depart()
        self.assertIn("mainland", msg)
        self.assertFalse(self.tm.active)
        self.assertIsNone(self.engine.current_dungeon)
        self.assertTrue(self.player.metadata.get("tutorial_done"))
        # Cast removed; player back on the overworld
        for nid in ("tut_willem", "tut_bors", "tut_dummy"):
            self.assertIsNone(self.engine.npc_manager.get_npc(nid))
        wmap = self.engine.world.map
        x, y = self.player.position
        self.assertTrue(0 <= x < wmap.width and 0 <= y < wmap.height)

    def test_fishing_works_on_island_shore(self):
        """Zone-aware gathering: the island's water counts."""
        # Stand on the dock (road over water — adjacent to zone water)
        self.player.position = (20, 8)
        msg = self.engine.forage()
        self.assertIn("fish", msg.lower())
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("raw_trout", ids)

    def test_no_encounters_on_island(self):
        self.engine.encounter_manager._cooldown_until = 0
        self.engine.encounter_manager.rng.random = lambda: 0.0
        self.assertIsNone(self.engine.encounter_manager.maybe_spawn())

    def test_hint_bar_carries_lesson(self):
        from ui.hints import context_hints
        hints = context_hints(self.engine)
        self.assertTrue(any("[Lesson]" in h for h in hints), hints)

    def test_tutorial_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="tut")
            self.engine.current_dungeon = None
            self.assertTrue(sm.load(self.engine, name="tut"))
            self.assertTrue(self.engine.tutorial_manager.active)
            self.assertEqual(self.engine.current_dungeon.name,
                             ISLAND_NAME)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_normal_games_skip_tutorial(self):
        engine2 = GameEngine(llm_provider="heuristic",
                             enable_npc_processes=False)
        engine2.start_game()
        try:
            self.assertFalse(engine2.tutorial_manager.active)
            self.assertIsNone(engine2.npc_manager.get_npc("tut_willem"))
        finally:
            engine2.end_game()


if __name__ == "__main__":
    unittest.main()
