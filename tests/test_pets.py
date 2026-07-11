"""Skilling pet tests (P2.6)."""

import unittest

from engine.game_engine import GameEngine
from engine.pets import PETS, BASE_ODDS, MIN_ODDS
from engine.skill_progression import add_skill_xp, total_xp_for_level


class TestPets(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.pets = self.engine.pet_system

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_every_skill_has_a_pet(self):
        from engine.skill_progression import SKILLS
        for sid in SKILLS:
            self.assertIn(sid, PETS, f"skill {sid} has no pet")

    def test_odds_improve_with_level(self):
        lvl1 = self.pets.odds_for("mining")
        add_skill_xp(self.player, "mining", total_xp_for_level(50))
        lvl50 = self.pets.odds_for("mining")
        self.assertLess(lvl50, lvl1)
        self.assertGreaterEqual(lvl50, MIN_ODDS)
        self.assertLessEqual(lvl1, BASE_ODDS)

    def test_award_announces_and_sets_active(self):
        self.pets.rng.randint = lambda a, b: 1  # force the jackpot
        msg = self.pets.maybe_award("fishing")
        self.assertIsNotNone(msg)
        self.assertIn("Bubbles", msg)
        self.assertIn("fishing", self.player.metadata["pets"])
        self.assertEqual(self.player.metadata["active_pet"], "fishing")
        pet = self.pets.active_pet()
        self.assertEqual(pet["name"], "Bubbles")

    def test_no_duplicate_pets(self):
        self.pets.rng.randint = lambda a, b: 1
        self.assertIsNotNone(self.pets.maybe_award("mining"))
        self.assertIsNone(self.pets.maybe_award("mining"),
                          "same pet must not drop twice")
        self.assertEqual(self.player.metadata["pets"].count("mining"), 1)

    def test_no_award_on_failed_roll(self):
        self.pets.rng.randint = lambda a, b: 2  # always miss
        self.assertIsNone(self.pets.maybe_award("mining"))
        self.assertNotIn("mining", self.player.metadata.get("pets", []))

    def test_follower_trails_one_step_behind(self):
        start = self.player.position
        moved = self.engine.move_player(1, 0) or \
            self.engine.move_player(0, 1) or self.engine.move_player(-1, 0)
        if not moved:
            self.skipTest("player boxed in")
        self.assertEqual(self.pets.follow_pos, start)

    def test_pets_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.pets.rng.randint = lambda a, b: 1
        self.pets.maybe_award("alchemy")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="p")
            self.player.metadata["pets"] = []
            self.player.metadata["active_pet"] = None
            self.assertTrue(sm.load(self.engine, name="p"))
            self.assertIn("alchemy",
                          self.engine.player.metadata["pets"])
            self.assertEqual(
                self.engine.pet_system.active_pet()["name"], "Fizz")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_collection_overlay_lists_pets(self):
        self.pets.rng.randint = lambda a, b: 1
        self.pets.maybe_award("mining")
        lines = self.engine.collection_log.overlay_lines()
        pet_line = next(ln for ln in lines if ln.startswith("Pets"))
        self.assertIn("Rocky", pet_line)
        self.assertIn(f"1/{len(PETS)}", pet_line)


if __name__ == "__main__":
    unittest.main()
