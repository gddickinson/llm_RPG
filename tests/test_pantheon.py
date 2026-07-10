"""Pantheon tests (P8.4) — deeds, prayer, miracles, omens."""

import random
import unittest

from engine.game_engine import GameEngine
from engine.pantheon import GODS, MIRACLE_COST, on_deed
from engine.player_deeds import record_deed


class TestPantheon(unittest.TestCase):
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

    def _favor(self):
        return self.player.metadata.setdefault("god_favor", {})

    def _stand_at_shrine(self):
        loc = next(l for l in self.engine.world.locations
                   if "shrine" in l.name.lower()
                   or "temple" in l.name.lower())
        wmap = self.engine.world.map
        wmap.remove_character(self.player)
        self.player.position = (loc.x, loc.y)
        wmap.place_character(self.player, loc.x, loc.y)

    def test_content_validates(self):
        self.assertGreaterEqual(len(GODS), 5)
        from items.data_validate import _check_pantheon
        self.assertEqual(_check_pantheon(), [])

    def test_deeds_build_favor(self):
        record_deed(self.engine, "slew a Wolf")
        self.assertEqual(self._favor().get("morrik"), 1)
        record_deed(self.engine, "harvested the ripe fields")
        self.assertEqual(self._favor().get("solara"), 1)
        record_deed(self.engine, "completed 'The Mire Beacon'")
        self.assertEqual(self._favor().get("veyra"), 1)

    def test_prayer_needs_a_holy_place(self):
        msg = self.engine.pray()
        self.assertIn("no holy place", msg)

    def test_one_prayer_per_day(self):
        self._stand_at_shrine()
        self.engine.pray()
        msg = self.engine.pray()
        self.assertIn("already prayed", msg)

    def test_quiet_prayer_builds_favor(self):
        self._stand_at_shrine()
        self._favor()["morrik"] = 3
        self.engine.pray()
        self.assertEqual(self._favor()["morrik"], 4)

    def test_miracle_spends_favor_heal(self):
        self._stand_at_shrine()
        self._favor()["solara"] = MIRACLE_COST + 2
        self.player.hp = 1
        msg = self.engine.pray()
        self.assertIn("Solara", msg)
        self.assertEqual(self.player.hp, self.player.max_hp)
        self.assertEqual(self._favor()["solara"], 2)

    def test_cure_miracle_clears_disease(self):
        from engine.disease import is_infected
        self.engine.disease.infect(self.player, "rot_cough")
        self._stand_at_shrine()
        self._favor()["pale_lady"] = MIRACLE_COST
        msg = self.engine.pray()
        self.assertIn("Pale Lady", msg)
        self.assertFalse(is_infected(self.player))

    def test_fortune_miracle_pays(self):
        self._stand_at_shrine()
        self._favor()["grimble"] = MIRACLE_COST
        gold = self.player.gold
        self.engine.pray()
        self.assertGreater(self.player.gold, gold)

    def test_deep_favor_brings_omens(self):
        self._favor()["morrik"] = 30
        self.engine.pantheon.rng = random.Random(1)
        omen = None
        for _ in range(20):
            omen = self.engine.pantheon.run_day()
            if omen:
                break
        self.assertIsNotNone(omen, "no omen in 20 nights of favor 30")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("[Realm]", log)

    def test_favor_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self._favor()["morrik"] = 7
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="gods")
            self._favor()["morrik"] = 0
            self.assertTrue(sm.load(self.engine, name="gods"))
            self.assertEqual(
                self.engine.player.metadata["god_favor"]["morrik"], 7)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
