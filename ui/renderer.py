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
    TerrainType.SCORCHED: "scorched", TerrainType.BRIDGE: "bridge",
}

# Door glyph colors by lock state (P9A.3b)
from ui.door_glyphs import DOOR_STATE_COLORS   # re-export (P9A.3b, split out)


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
        self._dim_shade = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
        self._dim_shade.fill((10, 10, 20, 130))   # cached fog-dim (P33.2)

    @staticmethod
    def active_zone(engine):
        """The alternate grid the player is inside, if any (dungeon or
        building interior — both carry a `terrain` grid)."""
        return getattr(engine, "current_dungeon", None) or \
            getattr(engine, "current_interior", None)

    def render(self, target: "pygame.Surface", engine, view_rect: "pygame.Rect"
               ) -> None:
        """Render the map into `target` within `view_rect`."""
        try:   # P34.7 the "Smooth sprites" (SSAA) setting toggles oversampling
            from engine import settings
            from ui import body_renderer as _br
            _br.SSAA_SCALE = 2 if settings.enabled(engine.player, "smooth") else 1
        except Exception:
            pass
        zone = self.active_zone(engine)
        # P41.3/P41.6 isometric render (overworld + interiors) behind the
        # LLM_RPG_RENDER=iso toggle; the engine + top-down path are untouched
        try:
            from ui import iso_render
            if iso_render.dispatch(self, target, engine, view_rect, zone):
                return
        except Exception:
            pass
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
                surf = self.sprites.tile_variant(sprite_name, wx, wy)
                target.blit(surf, dest)
                if dim:
                    target.blit(self._dim_shade, dest)

        ts = self.tile_size
        try:   # edge-blend seams + water coast (P33.2) then 2.5D blocks (P16.5)
            from ui.terrain_edges import draw_terrain_edges
            from ui.renderer_buildings import draw_buildings
            draw_terrain_edges(target, engine, view_rect, cam_x, cam_y, ts)
            draw_buildings(target, engine, view_rect, cam_x, cam_y, ts)
            from ui.scatter_draw import draw_scatter          # P39.6b props
            draw_scatter(target, engine, view_rect, cam_x, cam_y, ts)
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
        from ui.body_renderer import draw_body_crisp, draw_glimpsed, update_anim, draw_projectile  # noqa: E501
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
            (draw_glimpsed if glimpsed else draw_body_crisp)(
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
        from ui.door_glyphs import draw_door_glyphs
        draw_door_glyphs(target, engine, view_rect, cam_x, cam_y,
                         cols, rows, self.tile_size)

    def _render_zone(self, target, engine, view_rect, zone) -> None:
        """Draw a dungeon / interior grid instead of the overworld."""
        from ui.body_renderer import draw_body_crisp, update_anim
        px, py = engine.player.position
        cols = view_rect.width // self.tile_size
        rows = view_rect.height // self.tile_size
        cam_x = max(0, min(zone.width - cols, px - cols // 2))
        cam_y = max(0, min(zone.height - rows, py - rows // 2))

        # P39.2 each interior has a THEME (tomb = dark/dank, home = warm, …)
        from ui import interior_theme as itheme
        from world.world_map import TerrainType as _TT
        theme = itheme.theme_for(zone)
        is_dungeon = hasattr(zone, "rooms")
        target.fill(itheme.fill_color(theme), view_rect)

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
                dest = (view_rect.x + sx * self.tile_size,
                        view_rect.y + sy * self.tile_size)
                # P39.2 walls + the generic floor get the THEME material; other
                # terrains (water/road/cave) keep their own sprite
                themed = None
                if terrain == _TT.BUILDING:
                    themed = itheme.tile_surface(theme, "wall", self.tile_size)
                elif terrain == _TT.GRASS:
                    themed = itheme.tile_surface(theme, "floor", self.tile_size)
                if themed is not None:
                    target.blit(themed, dest)
                else:
                    sprite = _TERRAIN_TO_SPRITE.get(terrain, "grass")
                    target.blit(self.sprites.tile(sprite), dest)
                if visible is not None and (wx, wy) not in visible:
                    dim = pygame.Surface(
                        (self.tile_size, self.tile_size))
                    dim.set_alpha(160)
                    dim.fill((8, 6, 10))
                    target.blit(dim, dest)            # remembered, dim

        # P39.2 a faint mood wash over the whole room (dank blue / warm amber)
        mood = itheme.mood_overlay(theme, view_rect.width, view_rect.height)
        if mood is not None:
            target.blit(mood, (view_rect.x, view_rect.y))

        # Furniture (interiors)
        for furn in getattr(zone, "furniture", []):
            fx, fy = furn.get("x", -1), furn.get("y", -1)
            if not (cam_x <= fx < cam_x + cols and
                    cam_y <= fy < cam_y + rows):
                continue
            dest_x = view_rect.x + (fx - cam_x) * self.tile_size
            dest_y = view_rect.y + (fy - cam_y) * self.tile_size
            try:
                fname = furn.get("name", "?")
                if "stair" in fname.lower():        # P39.5 themed stairs
                    from ui.openings import draw_stairs, stair_kind_for
                    target.blit(draw_stairs(self.tile_size,
                                            stair_kind_for(theme)),
                                (dest_x, dest_y))
                else:
                    target.blit(self.sprites.furniture(fname),
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
            draw_body_crisp(target, char,
                      view_rect.x + (cx - cam_x) * self.tile_size,
                      view_rect.y + (cy - cam_y) * self.tile_size,
                      self.tile_size,
                      is_player=(char.id == engine.player.id))

        # P39.4 interior light & mood: warm pools around braziers/torches + the
        # hero, dust in dank rooms — makes a crypt feel dark, a home warm
        try:
            from ui import interior_light
            interior_light.draw(target, zone, view_rect, cam_x, cam_y,
                                self.tile_size, theme, engine.player.position)
        except Exception:
            pass

        # The ranged lock, underground too (P8.7)
        try:
            self._draw_reticle(target, engine, view_rect,
                               cam_x, cam_y, cols, rows)
        except Exception:
            pass

    def _draw_pet(self, target, pet: dict, x: int, y: int) -> None:
        from ui.renderer_overlays import draw_pet
        draw_pet(target, pet, x, y, self.tile_size)

    def _draw_hp_bar(self, target, char, x: int, y: int) -> None:
        from ui.renderer_overlays import draw_hp_bar
        draw_hp_bar(target, char, x, y, self.tile_size)

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
