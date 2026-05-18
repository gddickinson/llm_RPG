"""Tests for the weather system."""

import unittest

from engine.game_engine import GameEngine
from world.weather import Weather, WeatherSystem


class TestWeather(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_initial_weather_set(self):
        ws = self.engine.weather_system
        self.assertIsInstance(ws.state.current, Weather)

    def test_visibility_modifier_in_range(self):
        ws = self.engine.weather_system
        mod = ws.visibility_modifier()
        self.assertGreater(mod, 0.0)
        self.assertLessEqual(mod, 1.0)

    def test_tick_advances_with_time(self):
        ws = self.engine.weather_system
        before = ws.state.current
        # Advance well beyond the next roll
        self.engine.world.time = ws.state.next_roll_at + 10
        # Try a few times; weather may stay the same by chance
        # but next_roll_at should always update
        ws.tick()
        self.assertGreater(ws.state.next_roll_at,
                           self.engine.world.time - 10)

    def test_to_from_dict(self):
        ws = self.engine.weather_system
        ws.state.current = Weather.STORM
        ws.state.next_roll_at = 12345
        d = ws.to_dict()
        ws2 = WeatherSystem(self.engine)
        ws2.from_dict(d)
        self.assertEqual(ws2.state.current, Weather.STORM)
        self.assertEqual(ws2.state.next_roll_at, 12345)


if __name__ == "__main__":
    unittest.main()
