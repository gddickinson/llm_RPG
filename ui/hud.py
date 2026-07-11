"""HUD — status bars, mini-map, event log, dialog box, quest tracker."""

import logging
from typing import List

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.hud")


class HUD:
    """In-game heads-up display rendered over the map view."""

    def __init__(self, font_size: int = 14):
        if not PYGAME_OK:
            raise RuntimeError("pygame not installed")
        try:
            pygame.font.init()
            self.font = pygame.font.SysFont("monospace", font_size)
            self.big_font = pygame.font.SysFont("monospace", font_size + 4, bold=True)
        except Exception:
            self.font = None
            self.big_font = None

    # ---- panels --------------------------------------------------------

    def draw(self, target, engine, layout: dict) -> None:
        """Draw all HUD elements in their layout positions."""
        from engine import settings
        self.draw_status_panel(target, engine, layout["status"])
        self.draw_event_log(target, engine, layout["events"])
        self.draw_quest_panel(target, engine, layout["quests"])
        if settings.enabled(engine.player, "minimap"):
            self.draw_minimap(target, engine, layout["minimap"])
        if "map" in layout and settings.enabled(engine.player, "hints"):
            self.draw_hint_bar(target, engine, layout["map"])

    def draw_hint_bar(self, target, engine, map_rect) -> None:
        """Contextual key hints along the bottom edge of the map view."""
        if not self.font:
            return
        try:
            from ui.hints import context_hints
            hints = context_hints(engine)
        except Exception:
            hints = []
        if not hints:
            return
        text = "   ".join(hints)
        surf = self.font.render(text, True, (255, 235, 170))
        bar_h = surf.get_height() + 8
        bar = pygame.Surface((map_rect.width, bar_h), pygame.SRCALPHA)
        bar.fill((10, 10, 20, 190))
        target.blit(bar, (map_rect.x, map_rect.bottom - bar_h))
        target.blit(surf, (map_rect.x + 10,
                           map_rect.bottom - bar_h + 4))

    def draw_status_panel(self, target, engine, rect) -> None:
        self._panel(target, rect, "Status")
        p = engine.player
        from engine.leveling import xp_to_next
        xp = (p.metadata or {}).get("xp", 0)
        cur, need = xp_to_next(xp)

        lines = [
            f"Name: {p.name}",
            f"Class: {p.character_class.value} ({p.race.value})",
            f"Level: {p.level}",
        ]
        self._draw_lines(target, lines, rect, 8)

        # Level / XP bars positioned below text
        bar_y = rect.y + 26 + len(lines) * 16 + 4
        self._draw_bar(target, rect.x + 8, bar_y,
                       rect.width - 16, 10,
                       p.hp / max(1, p.max_hp), (200, 50, 50),
                       label=f"HP {p.hp}/{p.max_hp}")
        bar_y += 16
        ratio = (cur / need) if need > 0 else 1.0
        self._draw_bar(target, rect.x + 8, bar_y,
                       rect.width - 16, 10,
                       ratio, (90, 160, 230),
                       label=f"XP {cur}/{need}" if need else f"XP {xp} (MAX)")
        bar_y += 20

        more = [
            f"Gold: {p.gold}",
            f"Pos: {p.position}",
            f"Time: {engine.world.get_formatted_time()}",
        ]
        try:
            from characters.needs import need_descriptor
            condition = need_descriptor(p)
            if condition != "comfortable":
                more.append(f"Condition: {condition}")
        except Exception:
            pass
        try:
            party = engine.companion_manager.members()
        except Exception:
            party = []
        if party:
            more.append("Party:")
            for member in party:
                more.append(
                    f"  - {member.name} ({member.hp}/{member.max_hp})")
        more += ["", "Inventory:"]
        for it in p.inventory[:7]:
            name = it.name if hasattr(it, "name") else str(it)
            qty = getattr(it, "quantity", 1)
            more.append(f"  - {name}" + (f" x{qty}" if qty > 1 else ""))
        if len(p.inventory) > 7:
            more.append(f"  ... and {len(p.inventory) - 7} more")

        y = bar_y
        for line in more:
            self._text(target, line, (rect.x + 8, y))
            y += 16
            if y > rect.bottom - 16:
                break

    def _draw_bar(self, target, x: int, y: int, w: int, h: int,
                  ratio: float, color, label: str = "") -> None:
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(target, (40, 40, 50), (x, y, w, h))
        pygame.draw.rect(target, color, (x, y, int(w * ratio), h))
        pygame.draw.rect(target, (180, 180, 180), (x, y, w, h), 1)
        if label and self.font:
            surf = self.font.render(label, True, (220, 220, 220))
            target.blit(surf, (x + 4, y - 1))

    def draw_event_log(self, target, engine, rect) -> None:
        try:
            from engine.event_filter import filtered_recent, verbosity
            recent = filtered_recent(engine, 10)
            title = f"Event Log ({verbosity(engine)})"
        except Exception:
            recent = engine.memory_manager.get_recent_history(10)
            title = "Event Log"
        self._panel(target, rect, title)
        # Newest at bottom
        self._draw_lines(target, recent, rect, 8, max_lines=10)

    def draw_quest_panel(self, target, engine, rect) -> None:
        self._panel(target, rect, "Quests")
        if not engine.quest_manager:
            self._draw_lines(target, ["(quests disabled)"], rect, 8)
            return
        active = engine.quest_manager.active()
        completed = engine.quest_manager.completed()
        if not active and not completed:
            self._draw_lines(target, ["No quests."], rect, 8)
            return
        lines = []
        for q in active[:3]:
            lines.append(f"* {q.title}")
            for obj in q.objectives:
                mark = "[X]" if obj.is_complete() else "[ ]"
                lines.append(f"   {mark} {obj.description} ({obj.progress}/{obj.required})")
        if completed:
            lines.append("")
            lines.append(f"Completed: {len(completed)}")
        self._draw_lines(target, lines, rect, 8)

    def draw_minimap(self, target, engine, rect) -> None:
        self._panel(target, rect, "Map")
        wmap = engine.world.map
        cw = (rect.width - 8) // wmap.width
        ch = (rect.height - 24) // wmap.height
        scale = max(1, min(cw, ch))

        from world.world_map import TerrainType
        colors = {
            TerrainType.GRASS: (90, 150, 70),
            TerrainType.FOREST: (35, 90, 45),
            TerrainType.MOUNTAIN: (110, 100, 95),
            TerrainType.WATER: (45, 100, 180),
            TerrainType.ROAD: (160, 130, 90),
            TerrainType.BUILDING: (140, 100, 60),
            TerrainType.CAVE: (30, 30, 35),
            TerrainType.SWAMP: (62, 78, 52),
            TerrainType.FARMLAND: (124, 92, 56),
            TerrainType.RUBBLE: (105, 100, 95),
            TerrainType.SCORCHED: (48, 40, 36),
        }
        ox = rect.x + (rect.width - wmap.width * scale) // 2
        oy = rect.y + 20 + ((rect.height - 24) - wmap.height * scale) // 2
        for y in range(wmap.height):
            for x in range(wmap.width):
                color = colors.get(wmap.terrain[y][x], (50, 50, 50))
                pygame.draw.rect(target, color,
                                 (ox + x * scale, oy + y * scale,
                                  scale, scale))
        # Player marker
        px, py = engine.player.position
        pygame.draw.rect(target, (255, 240, 100),
                         (ox + px * scale, oy + py * scale,
                          max(2, scale), max(2, scale)))
        # NPCs
        for npc in engine.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            klass = getattr(npc.character_class, "value", "")
            color = (220, 80, 60) if klass in ("brigand", "troll", "monster") \
                else (140, 220, 220)
            nx, ny = npc.position
            pygame.draw.rect(target, color,
                             (ox + nx * scale, oy + ny * scale,
                              max(2, scale), max(2, scale)))

    # ---- modal overlays ----------------------------------------------

    def draw_dialog_box(self, target, screen_rect, npc_name: str,
                        text: str, prompt: str = "") -> None:
        h = 160
        box = pygame.Rect(20, screen_rect.height - h - 20,
                          screen_rect.width - 40, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 220))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (200, 180, 100), box, 2)
        self._text(target, npc_name, (box.x + 12, box.y + 8),
                   big=True, color=(255, 220, 120))
        # Wrap text
        words = (text or "").split()
        line = ""
        y = box.y + 36
        max_chars = box.width // 9
        for w in words:
            if len(line) + len(w) + 1 > max_chars:
                self._text(target, line, (box.x + 12, y))
                y += 18
                line = w
            else:
                line = (line + " " + w).strip()
        if line:
            self._text(target, line, (box.x + 12, y))
        if prompt:
            self._text(target, prompt, (box.x + 12, box.bottom - 22),
                       color=(180, 220, 255))

    def draw_text_overlay(self, target, screen_rect, title: str,
                          lines: List[str]) -> None:
        w = min(screen_rect.width - 60, 700)
        h = min(screen_rect.height - 60, 500)
        box = pygame.Rect((screen_rect.width - w) // 2,
                          (screen_rect.height - h) // 2, w, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 235))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (200, 180, 100), box, 2)
        self._text(target, title, (box.x + 16, box.y + 12),
                   big=True, color=(255, 220, 120))
        y = box.y + 50
        for line in lines:
            self._text(target, line, (box.x + 16, y))
            y += 18
            if y > box.bottom - 30:
                break
        self._text(target, "[ESC to close]",
                   (box.x + 16, box.bottom - 22), color=(180, 220, 255))

    def draw_help_overlay(self, target, screen_rect, title: str,
                          columns) -> None:
        """The controls reference, in two columns so every key fits on
        one screen (the single-column text overlay clipped half off the
        bottom, PUX.3)."""
        left, right = columns
        w = min(screen_rect.width - 40, 900)
        h = min(screen_rect.height - 40, 580)
        box = pygame.Rect((screen_rect.width - w) // 2,
                          (screen_rect.height - h) // 2, w, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 240))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (200, 180, 100), box, 2)
        self._text(target, title, (box.x + 16, box.y + 12),
                   big=True, color=(255, 220, 120))
        col_x = (box.x + 16, box.x + box.width // 2 + 8)
        for ci, lines in enumerate((left, right)):
            y = box.y + 48
            for line in lines:
                header = bool(line) and not line.startswith(" ")
                color = (255, 210, 120) if header else (215, 215, 225)
                self._text(target, line, (col_x[ci], y), color=color)
                y += 16
        self._text(target, "[ESC / F1 / ? to close]",
                   (box.x + 16, box.bottom - 22), color=(180, 220, 255))

    # ---- internals ----------------------------------------------------

    def _panel(self, target, rect, title: str) -> None:
        pygame.draw.rect(target, (20, 20, 30), rect)
        pygame.draw.rect(target, (200, 180, 100), rect, 1)
        self._text(target, title, (rect.x + 8, rect.y + 4),
                   big=True, color=(255, 220, 120))

    def _draw_lines(self, target, lines, rect, line_x: int,
                    max_lines: int = None) -> None:
        if not self.font:
            return
        y = rect.y + 26
        n = 0
        for line in lines[-max_lines:] if max_lines else lines:
            self._text(target, line, (rect.x + line_x, y))
            y += 16
            n += 1
            if y > rect.bottom - 16:
                break

    def _text(self, target, msg: str, pos, big: bool = False,
              color=(220, 220, 220)) -> None:
        if not self.font:
            return
        font = self.big_font if big and self.big_font else self.font
        surf = font.render(str(msg), True, color)
        target.blit(surf, pos)
