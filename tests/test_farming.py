"""Crop tests (P8.3) — fields live by the calendar."""

import unittest

from engine.game_engine import GameEngine
from world.calendar import DAY_MINUTES, MONTH_DAYS, minutes_from_date
from world.world_map import TerrainType


def _month_of(season):
    # calendar: months 1-3 spring, 4-6 summer, 7-9 autumn, 10-12 winter
    return {"spring": 1, "summer": 4, "autumn": 7, "winter": 10}[season]


class TestFarming(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.farms = self.engine.farm_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _set_season(self, season, day=5):
        self.engine.world.time = minutes_from_date(
            1, _month_of(season), day, 8, 0)

    def _run_days(self, n):
        for _ in range(n):
            self.engine.world.time += DAY_MINUTES
            self.farms.run_day()

    def test_farms_claim_fields(self):
        self.assertTrue(self.farms.plots,
                        "worldgen farms must get fields")
        (x, y) = next(iter(self.farms.plots))
        self.assertEqual(
            self.engine.world.map.get_terrain_at(x, y),
            TerrainType.FARMLAND)

    def test_spring_plants_summer_ripens(self):
        self._set_season("spring")
        self._run_days(2)
        states = {p["state"] for p in self.farms.plots.values()}
        self.assertIn("planted", states)
        self._run_days(50)          # into summer, past ripening
        states = {p["state"] for p in self.farms.plots.values()}
        self.assertIn("mature", states)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("Planting has begun", log)
        self.assertIn("golden", log)

    def test_player_harvest_yields_wheat(self):
        self._set_season("spring")
        self._run_days(52)
        pos = next(p for p, plot in self.farms.plots.items()
                   if plot["state"] == "mature")
        msg = self.farms.harvest(*pos)
        self.assertIn("harvest", msg.lower())
        names = [getattr(i, "id", "") for i in
                 self.engine.player.inventory]
        self.assertIn("wheat_sheaf", names)
        self.assertEqual(self.farms.state_at(*pos), "harvested")
        self.assertIsNone(self.farms.harvest(*pos),
                          "a field cannot be harvested twice")

    def test_farmers_bring_in_the_autumn_harvest(self):
        self._set_season("spring")
        self._run_days(52)          # mature by late summer
        stores_before = \
            self.engine.faction_ticker.state["villagers"]["stores"]
        self._set_season("autumn", day=15)
        self._run_days(12)
        states = {p["state"] for p in self.farms.plots.values()}
        self.assertEqual(states, {"harvested"})
        self.assertGreater(
            self.engine.faction_ticker.state["villagers"]["stores"],
            stores_before, "granaries must fill")

    def test_winter_returns_fields_to_fallow(self):
        self._set_season("spring")
        self._run_days(52)
        self._set_season("winter")
        self._run_days(1)
        states = {p["state"] for p in self.farms.plots.values()}
        self.assertEqual(states, {"fallow"})

    def test_forage_key_harvests(self):
        self._set_season("spring")
        self._run_days(52)
        pos = next(p for p, plot in self.farms.plots.items()
                   if plot["state"] == "mature")
        wmap = self.engine.world.map
        wmap.remove_character(self.engine.player)
        self.engine.player.position = pos
        wmap.place_character(self.engine.player, *pos)
        result = self.engine.forage()
        self.assertIn("wheat", result.lower())

    def test_plots_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self._set_season("spring")
        self._run_days(2)
        snapshot = {pos: p["state"]
                    for pos, p in self.farms.plots.items()}
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="farm")
            self.farms.plots = {}
            self.assertTrue(sm.load(self.engine, name="farm"))
            loaded = {pos: p["state"] for pos, p in
                      self.engine.farm_manager.plots.items()}
            self.assertEqual(loaded, snapshot)
            (x, y) = next(iter(loaded))
            self.assertEqual(
                self.engine.world.map.get_terrain_at(x, y),
                TerrainType.FARMLAND)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
