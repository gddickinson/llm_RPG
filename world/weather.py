"""Weather system — rain / fog / clear / snow tied to season.

Weather updates every N game-hours and biases the visibility range and
movement-tick narration. Visual effect (mist overlay) can be wired in
the renderer.
"""

import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from world.calendar import Season

logger = logging.getLogger("llm_rpg.weather")


class Weather(Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    FOG = "fog"
    SNOW = "snow"
    STORM = "storm"


# Per-season weather distribution (weighted)
SEASON_WEATHER = {
    Season.SPRING: [(Weather.CLEAR, 4), (Weather.CLOUDY, 3),
                    (Weather.RAIN, 3), (Weather.FOG, 1)],
    Season.SUMMER: [(Weather.CLEAR, 6), (Weather.CLOUDY, 2),
                    (Weather.STORM, 1)],
    Season.AUTUMN: [(Weather.CLEAR, 3), (Weather.CLOUDY, 3),
                    (Weather.RAIN, 2), (Weather.FOG, 2)],
    Season.WINTER: [(Weather.CLEAR, 2), (Weather.CLOUDY, 3),
                    (Weather.SNOW, 3), (Weather.FOG, 1), (Weather.STORM, 1)],
}


# Visibility multiplier per weather
VISIBILITY_MOD = {
    Weather.CLEAR: 1.0,
    Weather.CLOUDY: 1.0,
    Weather.RAIN: 0.85,
    Weather.FOG: 0.55,
    Weather.SNOW: 0.7,
    Weather.STORM: 0.5,
}


# How many minutes between weather rolls
WEATHER_TICK_MINUTES = 60 * 4   # every 4 game hours


def _weighted_pick(table, rng):
    total = sum(w for _, w in table)
    pick = rng.uniform(0, total)
    upto = 0.0
    for k, w in table:
        upto += w
        if pick <= upto:
            return k
    return table[-1][0]


@dataclass
class WeatherState:
    current: Weather = Weather.CLEAR
    next_roll_at: int = 0


class WeatherSystem:
    """Manages weather for the engine."""

    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.state = WeatherState()
        # Seed an initial weather appropriate for the starting season
        self._roll()

    def tick(self) -> Optional[str]:
        """Advance weather state. Return event string when it changes."""
        if self.engine.world.time < self.state.next_roll_at:
            return None
        prev = self.state.current
        self._roll()
        if self.state.current != prev:
            return f"The weather turns {self.state.current.value}."
        return None

    def _roll(self) -> None:
        season = self.engine.world.get_season()
        table = SEASON_WEATHER.get(season, SEASON_WEATHER[Season.SPRING])
        self.state.current = _weighted_pick(table, self.rng)
        self.state.next_roll_at = self.engine.world.time + WEATHER_TICK_MINUTES

    def visibility_modifier(self) -> float:
        return VISIBILITY_MOD.get(self.state.current, 1.0)

    def to_dict(self):
        return {"current": self.state.current.value,
                "next_roll_at": self.state.next_roll_at}

    def from_dict(self, d):
        try:
            self.state.current = Weather(d.get("current", "clear"))
        except ValueError:
            self.state.current = Weather.CLEAR
        self.state.next_roll_at = int(d.get("next_roll_at", 0))
