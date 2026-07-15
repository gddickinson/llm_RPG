"""Astronomy tests (P8.1) — real sky, two moons, omen nights."""

import unittest

from world.astronomy import (day_length, sunrise_sunset, solar_intensity,
                             moon_phase, phase_name, moons_tonight,
                             is_conjunction, moonlight, get_astronomy,
                             announce_conjunction, YEAR_LENGTH,
                             SUMMER_SOLSTICE)


def _conjunction_day(start=0, limit=1400):
    for day in range(start, start + limit):
        if is_conjunction(day):
            return day
    return None


class TestSun(unittest.TestCase):
    def test_summer_days_longer_than_winter(self):
        solstice_summer = day_length(SUMMER_SOLSTICE)
        solstice_winter = day_length(SUMMER_SOLSTICE +
                                     YEAR_LENGTH // 2)
        self.assertGreater(solstice_summer, 14.0)
        self.assertLess(solstice_winter, 10.0)

    def test_equinox_near_twelve_hours(self):
        self.assertAlmostEqual(day_length(0), 12.0, delta=0.6)

    def test_sunrise_before_sunset_and_centered_on_noon(self):
        rise, sset = sunrise_sunset(SUMMER_SOLSTICE)
        self.assertLess(rise, 0.5)
        self.assertGreater(sset, 0.5)
        self.assertAlmostEqual((rise + sset) / 2, 0.5, places=6)

    def test_solar_intensity_higher_in_summer(self):
        self.assertGreater(solar_intensity(SUMMER_SOLSTICE),
                           solar_intensity(SUMMER_SOLSTICE +
                                           YEAR_LENGTH // 2))

    def test_polar_latitudes_handled(self):
        self.assertEqual(day_length(SUMMER_SOLSTICE, latitude=85.0),
                         24.0)
        self.assertEqual(day_length(SUMMER_SOLSTICE +
                                    YEAR_LENGTH // 2, latitude=85.0),
                         0.0)


class TestMoons(unittest.TestCase):
    def test_phase_cycles(self):
        self.assertEqual(moon_phase(0, 28), 0.0)
        self.assertEqual(moon_phase(14, 28), 0.5)
        self.assertEqual(phase_name(0.5), "full")
        self.assertEqual(phase_name(0.0), "new")

    def test_two_moons_tonight(self):
        moons = moons_tonight(14)
        self.assertEqual([m["name"] for m in moons],
                         ["Lunara", "Thal"])
        self.assertEqual(moons[0]["phase_name"], "full")

    def test_conjunction_exists_and_is_rare(self):
        day = _conjunction_day()
        self.assertIsNotNone(day, "no conjunction in ~4 years?")
        nights = sum(1 for d in range(1400) if is_conjunction(d))
        self.assertLess(nights, 60, "conjunctions must stay rare")

    def test_moonlight_brighter_at_full(self):
        self.assertGreater(moonlight(14), moonlight(1))
        for d in (0, 7, 14, 100, 1000):
            self.assertGreaterEqual(moonlight(d), 0.0)
            self.assertLessEqual(moonlight(d), 1.0)

    def test_summary_dict(self):
        astro = get_astronomy(14)
        for key in ("day_length_hours", "sunrise", "sunset", "moons",
                    "conjunction", "moonlight", "solar_intensity"):
            self.assertIn(key, astro)


class TestIntegration(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_conjunction_becomes_an_omen_event(self):
        day = _conjunction_day()
        self.assertTrue(announce_conjunction(self.engine, day))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("Conjunction", log)
        self.assertTrue(any("Conjunction" in r for r in
                            self.engine.world_director.rumors))

    def test_ordinary_night_is_no_omen(self):
        day = _conjunction_day()
        quiet = next(d for d in range(1400) if not is_conjunction(d))
        self.assertFalse(announce_conjunction(self.engine, quiet))

    def test_conjunction_raises_encounter_danger(self):
        day = _conjunction_day()
        em = self.engine.encounter_manager
        self.engine.world.time = day * 24 * 60
        dangerous = em.spawn_chance()
        quiet = next(d for d in range(1400) if not is_conjunction(d))
        self.engine.world.time = quiet * 24 * 60
        ordinary = em.spawn_chance()
        self.assertGreater(dangerous, ordinary)

    def test_nightly_stack_announces_conjunction(self):
        day = _conjunction_day(start=2)
        self.engine.world.time = day * 24 * 60 + 60
        self.engine.advance_turn()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-30:])
        self.assertIn("Conjunction", log)


if __name__ == "__main__":
    unittest.main()
