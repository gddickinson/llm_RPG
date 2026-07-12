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
    TerrainType.SWAMP: "swamp",
    TerrainType.FARMLAND: "farmland",
    TerrainType.RUBBLE: "rubble",
    TerrainType.SCORCHED: "scorched",
}

# Door glyph colors by lock state (P9A.3b)
DOOR_STATE_COLORS = {
    "open": (110, 75, 40),
    "closed": (130, 95, 55),
    "locked": (95, 70, 50),
    "broken": (60, 45, 30),
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

    @staticmethod
    def active_zone(engine):
        """The alternate grid the player is inside, if any (dungeon or
        building interior — both carry a `terrain` grid)."""
        return getattr(engine, "current_dungeon", None) or \
            getattr(engine, "current_interior", None)

    def render(self, target: "pygame.Surface", engine, view_rect: "pygame.Rect"
               ) -> None:
        """Render the map into `target` within `view_rect`."""
        zone = self.active_zone(engine)
        if zone is not None:
            self._render_zone(target, engine, view_rect, zone)
            return
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
                dest = (view_rect.x + screen_x * self.tile_size,
                        view_rect.y + screen_y * self.tile_size)
                # Fog of war (P15.11): unseen black, explored dim
                try:
                    from engine.discovery import (is_explored,
                                                  is_visible)
                    if not is_explored(engine, wx, wy):
                        target.fill((8, 8, 12), (dest[0], dest[1],
                                    self.tile_size, self.tile_size))
                        continue
                    dim = not is_visible(engine, wx, wy)
                except Exception:
                    dim = False
                terrain = wmap.terrain[wy][wx]
                sprite_name = _TERRAIN_TO_SPRITE.get(terrain, "grass")
                surf = self.sprites.tile(sprite_name)
                target.blit(surf, dest)
                if dim:
                    shade = pygame.Surface(
                        (self.tile_size, self.tile_size),
                        pygame.SRCALPHA)
                    shade.fill((10, 10, 20, 130))
                    target.blit(shade, dest)

        try:   # 2.5D building blocks over the flat tiles (P16.5)
            from ui.renderer_buildings import draw_buildings
            draw_buildings(target, engine, view_rect, cam_x, cam_y,
                           self.tile_size)
        except Exception:
            pass

        # Surfaces: fire / oil / water overlays (P10.3); P15.2 flicker
        try:
            from ui.animation import surface_fill
            clk = pygame.time.get_ticks() / 1000.0
            for (sx2, sy2), s in \
                    engine.surfaces_layer.surfaces.items():
                if not (cam_x <= sx2 < cam_x + cols and
                        cam_y <= sy2 < cam_y + rows):
                    continue
                overlay = pygame.Surface(
                    (self.tile_size, self.tile_size), pygame.SRCALPHA)
                overlay.fill(surface_fill(s["kind"], clk))
                target.blit(overlay,
                            (view_rect.x + (sx2 - cam_x) *
                             self.tile_size,
                             view_rect.y + (sy2 - cam_y) *
                             self.tile_size))
        except Exception:
            pass

        # Building doors, colored by lock state (P9A.3b)
        self._draw_door_glyphs(target, engine, view_rect,
                               cam_x, cam_y, cols, rows)

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
        from ui.body_renderer import draw_body, draw_glimpsed, update_anim, draw_projectile  # noqa: E501
        from engine.presence import hidden_by_walls, is_indoors
        all_chars = list(engine.npc_manager.npcs.values()) + [engine.player]
        for char in all_chars:
            if hasattr(char, "is_active") and not char.is_active():
                continue
            # No seeing through walls (P9A.7) — unless keen_sight pierces
            # them (P14.2 magical sight)
            try:
                if hidden_by_walls(engine, char):
                    continue
            except Exception:
                pass
            # Fog (P15.11): actors on unseen tiles aren't drawn
            try:
                from engine.discovery import actor_hidden
                if char.id != engine.player.id and \
                        actor_hidden(engine, char):
                    continue
            except Exception:
                pass
            cx, cy = char.position
            if not (cam_x <= cx < cam_x + cols and cam_y <= cy < cam_y + rows):
                continue
            update_anim(char, 1.0 / 30.0)
            sx = view_rect.x + (cx - cam_x) * self.tile_size
            sy = view_rect.y + (cy - cam_y) * self.tile_size
            # heroes draw as heroes; an NPC glimpsed through a window is glazed
            is_player = char.id == engine.player.id or \
                (getattr(char, "metadata", {}) or {}).get("player_char",
                                                          False)
            try:
                glimpsed = not is_player and bool(is_indoors(engine, char))
            except Exception:
                glimpsed = False
            (draw_glimpsed if glimpsed else draw_body)(
                target, char, sx, sy, self.tile_size, is_player=is_player)

        # The ranged lock (P8.7)
        try:
            self._draw_reticle(target, engine, view_rect,
                               cam_x, cam_y, cols, rows)
        except Exception:
            pass

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

    def _draw_reticle(self, target, engine, view_rect,
                      cam_x, cam_y, cols, rows) -> None:
        """Gold corner brackets over the locked ranged target (P8.7)."""
        tid = getattr(engine, "player_target_id", None)
        if not tid:
            return
        npc = engine.npc_manager.npcs.get(tid)
        if npc is None or not npc.is_active():
            return
        tx, ty = npc.position
        if not (cam_x <= tx < cam_x + cols and
                cam_y <= ty < cam_y + rows):
            return
        ts = self.tile_size
        x = view_rect.x + (tx - cam_x) * ts
        y = view_rect.y + (ty - cam_y) * ts
        gold = (235, 195, 60)
        arm = max(4, ts // 4)
        for cx, cy, dx, dy in ((x, y, 1, 1), (x + ts, y, -1, 1),
                               (x, y + ts, 1, -1),
                               (x + ts, y + ts, -1, -1)):
            pygame.draw.line(target, gold, (cx, cy),
                             (cx + dx * arm, cy), 2)
            pygame.draw.line(target, gold, (cx, cy),
                             (cx, cy + dy * arm), 2)

    def _draw_door_glyphs(self, target, engine, view_rect,
                          cam_x, cam_y, cols, rows) -> None:
        """A visible door on every enterable building's face, colored
        by its lock state (P9A.3b)."""
        ts = self.tile_size
        for loc in getattr(engine.world, "locations", []):
            if loc.name not in getattr(engine, "interiors", {}):
                continue
            dx = loc.x + loc.width // 2
            dy = loc.y + loc.height - 1
            if not (cam_x <= dx < cam_x + cols and
                    cam_y <= dy < cam_y + rows):
                continue
            try:
                door = engine.door_manager.door(loc.name)
                state = engine.door_manager._effective_state(door)
            except Exception:
                state = "open"
            color = DOOR_STATE_COLORS.get(state, (110, 75, 40))
            sx = view_rect.x + (dx - cam_x) * ts
            sy = view_rect.y + (dy - cam_y) * ts
            w, h = max(6, ts // 3), max(9, ts // 2)
            rect = (sx + (ts - w) // 2, sy + ts - h, w, h)
            pygame.draw.rect(target, color, rect, border_radius=2)
            pygame.draw.rect(target, (25, 18, 10), rect, 1,
                             border_radius=2)
            if state == "locked":
                pygame.draw.circle(target, (210, 200, 90),
                                   (rect[0] + w // 2,
                                    rect[1] + h // 2), 2)
            elif state == "open":
                pygame.draw.rect(target, (15, 12, 8),
                                 (rect[0] + 2, rect[1] + 2,
                                  w - 4, h - 2))
            elif state == "broken":
                pygame.draw.line(target, (15, 12, 8),
                                 (rect[0], rect[1]),
                                 (rect[0] + w, rect[1] + h), 2)

    def _render_zone(self, target, engine, view_rect, zone) -> None:
        """Draw a dungeon / interior grid instead of the overworld."""
        from ui.body_renderer import draw_body, update_anim
        px, py = engine.player.position
        cols = view_rect.width // self.tile_size
        rows = view_rect.height // self.tile_size
        cam_x = max(0, min(zone.width - cols, px - cols // 2))
        cam_y = max(0, min(zone.height - rows, py - rows // 2))

        # Dungeons feel like rock; interiors like lamplit rooms
        is_dungeon = hasattr(zone, "rooms")
        target.fill((12, 10, 14) if is_dungeon else (24, 18, 12),
                    view_rect)

        # Dungeon fog-of-war (P8.6): shadowcast what the hero sees
        visible = None
        explored = None
        if is_dungeon or getattr(zone, "dark", False):
            try:
                from world.fov import zone_fov
                visible = zone_fov(zone, (px, py), radius=8)
                explored = getattr(zone, "explored", None)
                if explored is None:
                    explored = set()
                    zone.explored = explored
                explored.update(visible)
            except Exception:
                visible = None

        for sy in range(rows):
            for sx in range(cols):
                wx, wy = cam_x + sx, cam_y + sy
                if not (0 <= wx < zone.width and 0 <= wy < zone.height):
                    continue
                if visible is not None and (wx, wy) not in visible:
                    if (wx, wy) not in explored:
                        continue                      # never seen: dark
                terrain = zone.terrain[wy][wx]
                sprite = _TERRAIN_TO_SPRITE.get(terrain, "grass")
                dest = (view_rect.x + sx * self.tile_size,
                        view_rect.y + sy * self.tile_size)
                target.blit(self.sprites.tile(sprite), dest)
                if visible is not None and (wx, wy) not in visible:
                    dim = pygame.Surface(
                        (self.tile_size, self.tile_size))
                    dim.set_alpha(160)
                    dim.fill((8, 6, 10))
                    target.blit(dim, dest)            # remembered, dim

        # Furniture (interiors)
        for furn in getattr(zone, "furniture", []):
            fx, fy = furn.get("x", -1), furn.get("y", -1)
            if not (cam_x <= fx < cam_x + cols and
                    cam_y <= fy < cam_y + rows):
                continue
            dest_x = view_rect.x + (fx - cam_x) * self.tile_size
            dest_y = view_rect.y + (fy - cam_y) * self.tile_size
            try:
                target.blit(
                    self.sprites.furniture(furn.get("name", "?")),
                    (dest_x, dest_y))
            except Exception:
                pygame.draw.rect(
                    target, (120, 90, 50),
                    (dest_x + 4, dest_y + 4,
                     self.tile_size - 8, self.tile_size - 8))

        # Ground items at zone-local coordinates
        try:
            for (gx, gy), items in engine.world.ground_items.items():
                if not items or not (cam_x <= gx < cam_x + cols and
                                     cam_y <= gy < cam_y + rows):
                    continue
                if not (0 <= gx < zone.width and 0 <= gy < zone.height):
                    continue
                name = getattr(items[0], "name", str(items[0]))
                target.blit(self.sprites.item(name),
                            (view_rect.x + (gx - cam_x) * self.tile_size,
                             view_rect.y + (gy - cam_y) * self.tile_size))
        except Exception:
            pass

        # Characters: the player, monsters in dungeons, and everyone
        # who is INSIDE this building (P9A.7 — same entities, shown
        # at their interior positions)
        chars = [(engine.player, engine.player.position)]
        if is_dungeon:
            zname_d = getattr(zone, "name", None)
            chars += [(n, n.position)
                      for n in engine.npc_manager.npcs.values()
                      if n.is_active() and
                      n.id.startswith(("enc_", "tut_"))
                      and 0 <= n.position[0] < zone.width
                      and 0 <= n.position[1] < zone.height
                      # its own floor only (P9.5)
                      and n.metadata.get("zone") in (None, zname_d)]
        for npc_id, spot in getattr(zone, "visitors", {}).items():
            npc = engine.npc_manager.npcs.get(npc_id)
            if npc is not None and npc.is_active():
                chars.append((npc, spot))
        # Zone natives: structure monsters live at zone coords (P9.1)
        zname = getattr(zone, "name", None)
        if zname:
            chars += [(n, n.position)
                      for n in engine.npc_manager.npcs.values()
                      if n.is_active()
                      and n.metadata.get("zone") == zname]
        for char, (cx, cy) in chars:
            if not (cam_x <= cx < cam_x + cols and
                    cam_y <= cy < cam_y + rows):
                continue
            # Unseen monsters stay unseen (P8.6 fog-of-war)
            if visible is not None and (cx, cy) not in visible and \
                    char.id != engine.player.id:
                continue
            update_anim(char, 1.0 / 30.0)
            draw_body(target, char,
                      view_rect.x + (cx - cam_x) * self.tile_size,
                      view_rect.y + (cy - cam_y) * self.tile_size,
                      self.tile_size,
                      is_player=(char.id == engine.player.id))

        # The ranged lock, underground too (P8.7)
        try:
            self._draw_reticle(target, engine, view_rect,
                               cam_x, cam_y, cols, rows)
        except Exception:
            pass

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
