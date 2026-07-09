"""Map renderer — draws the world map (tiles, sprites, lighting overlays)."""

import logging
from typing import Any, Tuple

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

from world.world_map import TerrainType
from ui.sprite_loader import SpriteLoader

logger = logging.getLogger("llm_rpg.renderer")


# Map TerrainType -> sprite name
_TERRAIN_TO_SPRITE = {
    TerrainType.GRASS: "grass",
    TerrainType.FOREST: "forest",
    TerrainType.MOUNTAIN: "mountain",
    TerrainType.WATER: "water",
    TerrainType.ROAD: "road",
    TerrainType.BUILDING: "building",
    TerrainType.CAVE: "cave",
}


class MapRenderer:
    """Draws the world map onto a target Surface."""

    def __init__(self, tile_size: int = 32):
        if not PYGAME_OK:
            raise RuntimeError("pygame not installed")
        self.tile_size = tile_size
        self.sprites = SpriteLoader(tile_size=tile_size)
        # Time-of-day overlay cache
        self._tod_overlay = None
        self._tod_for = None
        # Lighting + weather overlays (lazy)
        self._lighting = None
        self._weather_overlay = None

    def render(self, target: "pygame.Surface", engine, view_rect: "pygame.Rect"
               ) -> None:
        """Render the map into `target` within `view_rect`."""
        world = engine.world
        wmap = world.map
        px, py = engine.player.position

        # Camera: keep player roughly centered
        cols = view_rect.width // self.tile_size
        rows = view_rect.height // self.tile_size
        cam_x = max(0, min(wmap.width - cols, px - cols // 2))
        cam_y = max(0, min(wmap.height - rows, py - rows // 2))

        # Background
        target.fill((20, 20, 25), view_rect)

        # Tiles
        for screen_y in range(rows):
            for screen_x in range(cols):
                wx = cam_x + screen_x
                wy = cam_y + screen_y
                if not (0 <= wx < wmap.width and 0 <= wy < wmap.height):
                    continue
                terrain = wmap.terrain[wy][wx]
                sprite_name = _TERRAIN_TO_SPRITE.get(terrain, "grass")
                surf = self.sprites.tile(sprite_name)
                dest = (view_rect.x + screen_x * self.tile_size,
                        view_rect.y + screen_y * self.tile_size)
                target.blit(surf, dest)

        # Ground items
        if hasattr(world, "ground_items"):
            for (gx, gy), items in world.ground_items.items():
                if not (cam_x <= gx < cam_x + cols and cam_y <= gy < cam_y + rows):
                    continue
                if not items:
                    continue
                name = items[0].name if hasattr(items[0], "name") else str(items[0])
                surf = self.sprites.item(name)
                target.blit(surf,
                            (view_rect.x + (gx - cam_x) * self.tile_size,
                             view_rect.y + (gy - cam_y) * self.tile_size))

        # Characters (NPCs + player) — procedural body renderer
        from ui.body_renderer import draw_body, update_anim, draw_projectile
        all_chars = list(engine.npc_manager.npcs.values()) + [engine.player]
        for char in all_chars:
            if hasattr(char, "is_active") and not char.is_active():
                continue
            cx, cy = char.position
            if not (cam_x <= cx < cam_x + cols and cam_y <= cy < cam_y + rows):
                continue
            update_anim(char, 1.0 / 30.0)
            sx = view_rect.x + (cx - cam_x) * self.tile_size
            sy = view_rect.y + (cy - cam_y) * self.tile_size
            is_player = char.id == engine.player.id
            draw_body(target, char, sx, sy, self.tile_size, is_player=is_player)

        # Skilling pet follower (small cosmetic critter behind the player)
        try:
            pet = engine.pet_system.active_pet()
            pos = engine.pet_system.follow_pos
            if pet and pos and cam_x <= pos[0] < cam_x + cols \
                    and cam_y <= pos[1] < cam_y + rows:
                psx = view_rect.x + (pos[0] - cam_x) * self.tile_size
                psy = view_rect.y + (pos[1] - cam_y) * self.tile_size
                self._draw_pet(target, pet, psx, psy)
        except Exception:
            pass

        # In-flight projectiles
        try:
            for proj in engine.projectile_manager.active:
                if not (cam_x <= proj.x < cam_x + cols
                        and cam_y <= proj.y < cam_y + rows):
                    continue
                psx = view_rect.x + int((proj.x - cam_x) * self.tile_size)
                psy = view_rect.y + int((proj.y - cam_y) * self.tile_size)
                draw_projectile(target, proj.kind, psx, psy, self.tile_size)
        except Exception:
            pass

        # Lighting overlay (darkness at night, torchlight, window glow)
        try:
            if self._lighting is None:
                from ui.lighting import LightingOverlay
                self._lighting = LightingOverlay()
            self._lighting.apply(target, view_rect, engine,
                                 cam_x, cam_y, self.tile_size)
        except Exception:
            # Fall back to flat tod overlay
            self._apply_tod_overlay(target, view_rect,
                                    engine.world.get_time_of_day())

        # Weather particle overlay
        try:
            if self._weather_overlay is None:
                from ui.weather_overlay import WeatherOverlay
                self._weather_overlay = WeatherOverlay()
            weather_kind = engine.weather_system.state.current.value
            self._weather_overlay.update(1.0 / 30.0, weather_kind, view_rect)
            self._weather_overlay.draw(target, view_rect)
        except Exception:
            pass

        # Combat effects overlay (damage popups, particles, hit flashes)
        try:
            ce = getattr(engine, "combat_effects", None)
            if ce:
                ce.update(1.0 / 30.0)
                ce.draw(target, view_rect, cam_x, cam_y, self.tile_size)
        except Exception:
            pass

    # ---- helpers ------------------------------------------------------

    def _draw_pet(self, target, pet: dict, x: int, y: int) -> None:
        """A tiny bobbing critter: colored body + eyes."""
        ts = self.tile_size
        color = tuple(pet.get("color", (200, 200, 200)))
        cx = x + ts // 2
        cy = y + int(ts * 0.68)
        r = max(3, ts // 5)
        pygame.draw.circle(target, color, (cx, cy), r)
        dark = tuple(max(0, c - 70) for c in color)
        pygame.draw.circle(target, dark, (cx, cy), r, 1)
        eye = max(1, ts // 20)
        pygame.draw.circle(target, (20, 20, 25),
                           (cx - r // 2, cy - eye), eye)
        pygame.draw.circle(target, (20, 20, 25),
                           (cx + r // 2, cy - eye), eye)

    def _draw_hp_bar(self, target, char, x: int, y: int) -> None:
        w = self.tile_size - 4
        h = 3
        ratio = max(0.0, char.hp / max(1, char.max_hp))
        pygame.draw.rect(target, (60, 0, 0),
                         (x + 2, y - 5, w, h))
        pygame.draw.rect(target, (200, 50, 50),
                         (x + 2, y - 5, int(w * ratio), h))

    def _apply_tod_overlay(self, target, rect, time_of_day: str) -> None:
        # Recompute overlay only when TOD changes
        if self._tod_for != time_of_day or self._tod_overlay is None \
                or self._tod_overlay.get_size() != (rect.width, rect.height):
            colors = {
                "morning":   (255, 200, 120, 25),
                "afternoon": (255, 255, 255, 0),
                "evening":   (255, 150, 100, 50),
                "night":     (10, 10, 70, 110),
            }
            color = colors.get(time_of_day, (255, 255, 255, 0))
            overlay = pygame.Surface((rect.width, rect.height),
                                     pygame.SRCALPHA)
            overlay.fill(color)
            self._tod_overlay = overlay
            self._tod_for = time_of_day
        if self._tod_overlay.get_alpha() != 0:
            target.blit(self._tod_overlay, (rect.x, rect.y))
