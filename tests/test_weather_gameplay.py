"""Weather must affect gameplay, not just visuals (P0.5).

Covers: effective visibility shrinks in bad weather, encounter chance
rises in poor visibility, and storms/snow slow off-road travel.
"""

import unittest

from engine.game_engine import GameEngine
from world.weather import Weather
from world.world_map import TerrainType


class TestWeatherGameplay(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _set_weather(self, weather: Weather):
        self.engine.weather_system.state.current = weather
        # Prevent a re-roll from overwriting our forced weather
        self.engine.weather_system.state.next_roll_at = \
            self.engine.world.time + 10_000

    def test_effective_visibility_shrinks_in_fog(self):
        self._set_weather(Weather.CLEAR)
        clear = self.engine.effective_visibility()
        self._set_weather(Weather.FOG)
        fog = self.engine.effective_visibility()
        self.assertLess(fog, clear)
        self.assertGreaterEqual(fog, 2, "visibility floor of 2 tiles")

    def test_encounter_chance_rises_in_storm(self):
        em = self.engine.encounter_manager
        self._set_weather(Weather.CLEAR)
        clear = em.spawn_chance()
        self._set_weather(Weather.STORM)
        storm = em.spawn_chance()
        self.assertGreater(storm, clear)
        self.assertAlmostEqual(storm / clear, 1.5, places=2)

    def test_storm_slows_offroad_travel(self):
        player = self.engine.player
        wmap = self.engine.world.map

        # Find a grass tile with a grass neighbor to walk onto
        def place_on_grass():
            for y in range(1, wmap.height - 1):
                for x in range(1, wmap.width - 1):
                    if wmap.get_terrain_at(x, y) == TerrainType.GRASS and \
                            wmap.get_terrain_at(x + 1, y) == TerrainType.GRASS:
                        player.position = (x, y)
                        wmap.place_character(player, x, y)
                        return True
            return False

        if not place_on_grass():
            self.skipTest("no adjacent grass tiles found")

        self._set_weather(Weather.CLEAR)
        t0 = self.engine.world.time
        self.assertTrue(self.engine.move_player(1, 0))
        clear_cost = self.engine.world.time - t0

        self.assertTrue(place_on_grass())
        self._set_weather(Weather.STORM)
        t0 = self.engine.world.time
        self.assertTrue(self.engine.move_player(1, 0))
        storm_cost = self.engine.world.time - t0

        self.assertGreater(storm_cost, clear_cost,
                           "storm should cost extra time off-road")

    def test_storm_does_not_slow_road_travel(self):
        player = self.engine.player
        wmap = self.engine.world.map
        road = None
        for y in range(1, wmap.height - 1):
            for x in range(1, wmap.width - 1):
                if wmap.get_terrain_at(x, y) == TerrainType.ROAD and \
                        wmap.get_terrain_at(x + 1, y) == TerrainType.ROAD:
                    road = (x, y)
                    break
            if road:
                break
        if road is None:
            self.skipTest("no adjacent road tiles found")
        player.position = road
        wmap.place_character(player, *road)

        self._set_weather(Weather.STORM)
        t0 = self.engine.world.time
        self.assertTrue(self.engine.move_player(1, 0))
        self.assertEqual(self.engine.world.time - t0, 1,
                         "roads stay full speed in storms")


if __name__ == "__main__":
    unittest.main()
