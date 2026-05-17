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

        # Characters (NPCs + player) — only active
        all_chars = list(engine.npc_manager.npcs.values()) + [engine.player]
        for char in all_chars:
            if hasattr(char, "is_active") and not char.is_active():
                continue
            cx, cy = char.position
            if not (cam_x <= cx < cam_x + cols and cam_y <= cy < cam_y + rows):
                continue
            klass = getattr(getattr(char, "character_class", None), "value", "")
            is_player = char.id == engine.player.id
            is_hostile = klass in ("brigand", "troll", "monster")
            surf = self.sprites.character(klass, is_player=is_player,
                                          is_hostile=is_hostile)
            target.blit(surf,
                        (view_rect.x + (cx - cam_x) * self.tile_size,
                         view_rect.y + (cy - cam_y) * self.tile_size))
            # HP bar above hostile/non-player
            if not is_player and char.max_hp > 0:
                self._draw_hp_bar(target, char,
                                  view_rect.x + (cx - cam_x) * self.tile_size,
                                  view_rect.y + (cy - cam_y) * self.tile_size)

        # Time-of-day overlay
        self._apply_tod_overlay(target, view_rect, engine.world.get_time_of_day())

    # ---- helpers ------------------------------------------------------

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
