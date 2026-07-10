"""Occupants & homes tests (P9A.3)."""

import unittest

from engine.game_engine import GameEngine


class TestHomes(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.homes = self.engine.homes

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_preset_npcs_keep_their_homes(self):
        keeper = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.assertEqual(keeper.home_location, "Oakvale Tavern")

    def test_guard_moves_into_the_watch(self):
        guard = self.engine.npc_manager.get_npc("guard_01")
        self.assertIn("watchtower", guard.home_location.lower())

    def test_unowned_buildings_get_style_matched_residents(self):
        farm_locs = [l for l in self.engine.world.locations
                     if "farm" in l.name.lower()
                     and l.name in self.engine.interiors]
        self.assertTrue(farm_locs)
        for loc in farm_locs:
            occupants = self.homes.occupants_of(loc.name)
            self.assertTrue(occupants,
                            f"{loc.name} should have a resident")
            for npc in occupants:
                self.assertEqual(
                    getattr(npc.character_class, "value", ""),
                    "villager",
                    "farm residents are villagers")

    def test_library_gets_a_wizard(self):
        libs = [l for l in self.engine.world.locations
                if "library" in l.name.lower()
                and l.name in self.engine.interiors]
        if not libs:
            self.skipTest("no library generated this world")
        occupants = self.homes.occupants_of(libs[0].name)
        self.assertTrue(occupants)
        self.assertEqual(
            getattr(occupants[0].character_class, "value", ""),
            "wizard")

    def test_assignment_is_idempotent(self):
        before = len(self.engine.npc_manager.npcs)
        self.assertEqual(self.homes.assign(), 0,
                         "second assign must create nobody")
        self.assertEqual(len(self.engine.npc_manager.npcs), before)

    def test_residents_are_scheduled_home_at_night(self):
        from characters.schedules import current_entry
        farm_locs = [l for l in self.engine.world.locations
                     if "farm" in l.name.lower()
                     and l.name in self.engine.interiors]
        resident = self.homes.occupants_of(farm_locs[0].name)[0]
        entry = current_entry(
            getattr(resident.character_class, "value", "villager"), 23)
        self.assertEqual(entry[2], "home",
                         "23:00 schedule must point home")
        self.assertEqual(resident.home_location, farm_locs[0].name)

    def test_owner_and_derelict_queries(self):
        farm_locs = [l for l in self.engine.world.locations
                     if "farm" in l.name.lower()
                     and l.name in self.engine.interiors]
        self.assertIsNotNone(self.homes.owner_of(farm_locs[0].name))
        self.assertFalse(self.homes.is_derelict(farm_locs[0].name))

    def test_residents_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        farm_locs = [l for l in self.engine.world.locations
                     if "farm" in l.name.lower()
                     and l.name in self.engine.interiors]
        resident = self.homes.occupants_of(farm_locs[0].name)[0]
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="homes")
            self.assertTrue(sm.load(self.engine, name="homes"))
            loaded = self.engine.npc_manager.get_npc(resident.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.home_location, farm_locs[0].name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
