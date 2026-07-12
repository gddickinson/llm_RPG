"""Dynamic lighting overlay.

At night, the world is dark except for:
- A radial torchlight around the player (warm).
- A soft glow around every building tile (window light).

This is rendered as a single dark surface with bright "holes" carved out.
The blend mode is alpha-subtractive so the underlying world shows through.
"""

import logging
from typing import Tuple

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.lighting")


# Time-of-day -> ambient darkness alpha (0=clear day, 200=very dark night)
TOD_DARKNESS = {
    "morning": 0,
    "afternoon": 0,
    "evening": 80,
    "night": 170,
}


# Soft radial gradient surface cache keyed by (radius, color tuple)
_GRADIENT_CACHE: dict = {}


def _radial_light(radius: int, color: Tuple[int, int, int]) -> "pygame.Surface":
    """Cached radial gradient — bright center fading to transparent."""
    key = (radius, color)
    cached = _GRADIENT_CACHE.get(key)
    if cached is not None:
        return cached
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        alpha = int(255 * (1 - r / radius) ** 2)
        pygame.draw.circle(surf, (*color, alpha), (radius, radius), r)
    _GRADIENT_CACHE[key] = surf
    return surf


class LightingOverlay:
    """Renders the night darkness + light sources for a frame."""

    def __init__(self):
        self._overlay = None
        self._overlay_size = (0, 0)

    def apply(self, target, view_rect, engine,
              cam_x: int, cam_y: int, tile_size: int) -> None:
        """Darken `view_rect` for night and punch out bright spots."""
        if not PYGAME_OK:
            return

        tod = engine.world.get_time_of_day()
        # P15.2: ease the ambient darkness per-minute through dusk/dawn
        # instead of snapping between morning/evening/night. Fall back to
        # the discrete table if the pure helper is unavailable.
        try:
            from ui.animation import ambient_darkness
            darkness = ambient_darkness((engine.world.time % 1440) / 60.0)
        except Exception:
            darkness = TOD_DARKNESS.get(tod, 0)
        # Full moons lighten clear nights (P8.1)
        if tod == "night":
            try:
                from world.astronomy import moonlight
                day = engine.world.time // (24 * 60)
                darkness = max(100, darkness -
                               int(60 * moonlight(day)))
            except Exception:
                pass
        # Weather adds darkness
        try:
            weather = engine.weather_system.state.current.value
            if weather in ("storm", "fog"):
                darkness = min(220, darkness + 50)
            elif weather in ("rain", "cloudy"):
                darkness = min(200, darkness + 20)
        except Exception:
            pass

        if darkness <= 5:
            return

        size = (view_rect.width, view_rect.height)
        if self._overlay is None or self._overlay_size != size:
            self._overlay = pygame.Surface(size, pygame.SRCALPHA)
            self._overlay_size = size

        self._overlay.fill((0, 0, 30, darkness))

        # Player torchlight (warm); fog/storm shrink the lit radius
        try:
            vis_mod = engine.weather_system.visibility_modifier()
        except Exception:
            vis_mod = 1.0
        player = engine.player
        if player and player.is_alive():
            self._punch_light(
                player.position, view_rect, cam_x, cam_y, tile_size,
                radius_tiles=max(2.0, 4.5 * vis_mod),
                color=(255, 200, 100), strength=darkness)

        # Window glow on building tiles
        try:
            from world.world_map import TerrainType
            wmap = engine.world.map
            cols = view_rect.width // tile_size
            rows = view_rect.height // tile_size
            window_color = (255, 220, 120)
            for sy in range(rows):
                for sx in range(cols):
                    wx, wy = cam_x + sx, cam_y + sy
                    if not (0 <= wx < wmap.width and 0 <= wy < wmap.height):
                        continue
                    if wmap.terrain[wy][wx] == TerrainType.BUILDING:
                        self._punch_light(
                            (wx, wy), view_rect, cam_x, cam_y, tile_size,
                            radius_tiles=1.6, color=window_color,
                            strength=darkness * 0.7)
        except Exception:
            pass

        # Companion torches
        try:
            for ally in engine.companion_manager.members():
                if not ally.is_active():
                    continue
                self._punch_light(
                    ally.position, view_rect, cam_x, cam_y, tile_size,
                    radius_tiles=3.0, color=(255, 200, 100),
                    strength=darkness * 0.7)
        except Exception:
            pass

        # Coloured light sources (P15.4): marsh wisps glow blue-green
        try:
            from ui.light_palette import light_color
            for npc in engine.npc_manager.npcs.values():
                if not npc.is_active():
                    continue
                tag = (getattr(npc, "id", "") + " " +
                       getattr(npc, "name", "")).lower()
                if "wisp" in tag:
                    self._punch_light(
                        npc.position, view_rect, cam_x, cam_y, tile_size,
                        radius_tiles=2.4, color=light_color("wisp"),
                        strength=darkness * 0.75)
        except Exception:
            pass

        # Apply
        target.blit(self._overlay, view_rect.topleft)

        # The whole-sky wash: aurora on conjunction nights, winter chill
        # while it snows (P15.4).
        self._apply_sky_tint(target, view_rect, engine, size)

    def _apply_sky_tint(self, target, view_rect, engine, size) -> None:
        try:
            from ui.light_palette import sky_tint
            from world.astronomy import is_conjunction
            hour = (engine.world.time % 1440) / 60.0
            conj = is_conjunction(engine.world.time // (24 * 60))
            weather = engine.weather_system.state.current.value
            season = engine.world.get_date().season.value
            tint = sky_tint(hour, conjunction=conj, weather=weather,
                            season=season)
            if tint[3] > 0:
                wash = pygame.Surface(size, pygame.SRCALPHA)
                wash.fill(tint)
                target.blit(wash, view_rect.topleft)
        except Exception:
            pass

    # ------------------------------------------------------------------

    def _punch_light(self, world_pos, view_rect,
                     cam_x: int, cam_y: int, tile_size: int,
                     radius_tiles: float,
                     color: Tuple[int, int, int],
                     strength: float = 200) -> None:
        wx, wy = world_pos
        sx = (wx - cam_x) * tile_size + tile_size // 2
        sy = (wy - cam_y) * tile_size + tile_size // 2
        radius_px = max(8, int(radius_tiles * tile_size))
        gradient = _radial_light(radius_px, color)
        # Subtract from overlay alpha (blend BLEND_RGBA_SUB)
        # Scale gradient alpha by strength factor
        light = gradient.copy()
        if strength < 200:
            scale = strength / 200.0
            arr = pygame.surfarray.pixels_alpha(light)
            arr[...] = (arr * scale).astype(arr.dtype)
            del arr
        self._overlay.blit(light,
                           (sx - radius_px, sy - radius_px),
                           special_flags=pygame.BLEND_RGBA_SUB)
