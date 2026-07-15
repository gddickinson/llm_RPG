"""P41.10 — the projection-agnostic day-night + weather sky overlay."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from ui import sky_overlay


class _Cur:
    def __init__(self, value):
        self.value = value


class _WState:
    def __init__(self, value):
        self.current = _Cur(value)


class _Weather:
    def __init__(self, value="clear"):
        self.state = _WState(value)

    def visibility_modifier(self):
        return 1.0


class _Season:
    def __init__(self, value):
        self.value = value


class _Date:
    def __init__(self, season):
        self.season = _Season(season)


class _World:
    def __init__(self, time, season="summer"):
        self.time = time
        self._season = season

    def get_time_of_day(self):
        h = (self.time % 1440) / 60.0
        return "afternoon" if 6 <= h < 18 else "night"

    def get_date(self):
        return _Date(self._season)


class _Engine:
    def __init__(self, time, weather="clear", season="summer"):
        self.world = _World(time, season)
        self.weather_system = _Weather(weather)


def _brightness(surf, rect):
    x, y, w, h = rect
    tot = n = 0
    for px in range(x, x + w, 4):
        for py in range(y, y + h, 4):
            c = surf.get_at((px, py))
            tot += c[0] + c[1] + c[2]
            n += 1
    return tot / max(1, n)


class TestSkyOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_night_is_darker_than_noon(self):
        day = sky_overlay.night_darkness(_Engine(12 * 60))
        night = sky_overlay.night_darkness(_Engine(2 * 60))
        self.assertLess(day, night, "2am should be much darker than noon")
        self.assertGreater(night, 60)

    def test_weather_adds_darkness(self):
        clear = sky_overlay.night_darkness(_Engine(12 * 60, "clear"))
        fog = sky_overlay.night_darkness(_Engine(12 * 60, "fog"))
        self.assertGreater(fog, clear, "fog should darken the day")

    def test_apply_darkens_the_view_at_night(self):
        view = pygame.Rect(0, 0, 200, 200)
        day = pygame.Surface((200, 200))
        day.fill((120, 160, 90))
        sky_overlay.apply(day, view, _Engine(12 * 60, "clear"))
        night = pygame.Surface((200, 200))
        night.fill((120, 160, 90))
        sky_overlay.apply(night, view, _Engine(2 * 60, "clear"))
        self.assertLess(_brightness(night, (0, 0, 200, 200)),
                        _brightness(day, (0, 0, 200, 200)))

    def test_apply_is_a_safe_noop_at_bright_noon(self):
        view = pygame.Rect(0, 0, 100, 100)
        surf = pygame.Surface((100, 100))
        surf.fill((120, 160, 90))
        before = _brightness(surf, (0, 0, 100, 100))
        sky_overlay.apply(surf, view, _Engine(12 * 60, "clear"))
        # a clear summer noon adds no meaningful tint
        self.assertAlmostEqual(_brightness(surf, (0, 0, 100, 100)), before,
                               delta=6)

    def test_sky_wash_returns_none_or_rgba(self):
        w = sky_overlay.sky_wash(_Engine(2 * 60, "snow", "winter"))
        self.assertTrue(w is None or len(w) == 4)

    def test_weather_overlay_is_driven_when_supplied(self):
        from ui.weather_overlay import WeatherOverlay
        wo = WeatherOverlay()
        view = pygame.Rect(0, 0, 160, 160)
        surf = pygame.Surface((160, 160))
        surf.fill((0, 0, 0))
        # should not raise, and should paint some fog particles over black
        for _ in range(4):
            sky_overlay.apply(surf, view, _Engine(20 * 60, "fog"), wo)
        painted = sum(1 for x in range(0, 160, 6) for y in range(0, 160, 6)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 5, "fog particles should paint the view")


if __name__ == "__main__":
    unittest.main()
