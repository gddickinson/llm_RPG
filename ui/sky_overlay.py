"""P41.10 — projection-agnostic day-night + weather SKY overlay.

A flat full-view wash so the ISOMETRIC overworld reads night / rain / fog /
season like the top-down renderer: eased night DARKNESS (moon-lightened, with a
weather bump), the `sky_tint` WASH (green aurora on conjunction nights, a cold
winter chill), and the weather PARTICLE overlay. Kept flat + shared so both
projections darken and tint identically — the per-tile torch/window light
punches stay a top-down nicety, and interiors keep their own P41.9 light pass.
"""

import pygame


def night_darkness(engine) -> int:
    """Ambient darkness alpha (0..~220) for the current moment: eased night +
    moonlight relief + a weather bump. Pure over the engine clock & weather."""
    try:
        from ui.animation import ambient_darkness
        hour = (engine.world.time % 1440) / 60.0
        darkness = ambient_darkness(hour)
    except Exception:
        return 0
    try:                                   # full moons lighten clear nights
        if engine.world.get_time_of_day() == "night":
            from world.astronomy import moonlight
            day = engine.world.time // (24 * 60)
            darkness = max(100, darkness - int(60 * moonlight(day)))
    except Exception:
        pass
    try:                                   # weather adds darkness
        weather = engine.weather_system.state.current.value
        if weather in ("storm", "fog"):
            darkness = min(220, darkness + 50)
        elif weather in ("rain", "cloudy"):
            darkness = min(200, darkness + 20)
    except Exception:
        pass
    return int(darkness)


def sky_wash(engine):
    """The RGBA sky tint (aurora / winter chill) for this moment, or None."""
    try:
        from ui.light_palette import sky_tint
        from world.astronomy import is_conjunction
        hour = (engine.world.time % 1440) / 60.0
        conj = is_conjunction(engine.world.time // (24 * 60))
        weather = engine.weather_system.state.current.value
        season = engine.world.get_date().season.value
        return sky_tint(hour, conjunction=conj, weather=weather, season=season)
    except Exception:
        return None


def apply(target, view_rect, engine, weather_overlay=None) -> None:
    """Cast the day-night darkness + sky tint over the view, then the weather
    particles (if a persistent `WeatherOverlay` is supplied)."""
    darkness = night_darkness(engine)
    if darkness > 5:
        ov = pygame.Surface((view_rect.width, view_rect.height),
                            pygame.SRCALPHA)
        ov.fill((0, 0, 30, darkness))
        target.blit(ov, (view_rect.x, view_rect.y))

    tint = sky_wash(engine)
    if tint and len(tint) == 4 and tint[3] > 0:
        wash = pygame.Surface((view_rect.width, view_rect.height),
                              pygame.SRCALPHA)
        wash.fill(tint)
        target.blit(wash, (view_rect.x, view_rect.y))

    if weather_overlay is not None:
        try:
            weather = engine.weather_system.state.current.value
            weather_overlay.update(1.0 / 30.0, weather, view_rect)
            weather_overlay.draw(target, view_rect)
        except Exception:
            pass
