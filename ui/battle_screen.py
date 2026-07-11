"""Battle screen (P17.4) — the zoomable window onto a battle.

A standalone pygame view (like the start menu — no game engine
needed) that watches a `BattleSession` tick a staged scenario. It
is RENDER ONLY: the simulation already runs headless (P17.3); this
draws it, at a tile size that steps 8→16→32→48 with a float camera,
and drops to one blob-per-squad below 16px (level of detail). The
player can pan, zoom, play/pause, single-step and reset — a testbed
for the tactical layer before it folds into the world (P17.8).

Controls: SPACE play/pause · N step · R reset · +/- or wheel zoom ·
arrows/WASD pan · ESC/Q back to the menu.
"""

import logging
from typing import Optional

from engine.battle import BattleSession
from engine.battle.battle_scenario import build_field, team_strengths
from ui.battle_camera import (BattleCamera, category_shape,
                              marker_points)

logger = logging.getLogger("llm_rpg.battle.screen")

try:
    import pygame
    PYGAME_OK = True
except Exception:                     # pragma: no cover
    PYGAME_OK = False

# terrain kind -> colour
_TERRAIN = {
    "grass": (58, 96, 58), "road": (140, 122, 84),
    "rubble": (108, 100, 94), "scorched": (56, 48, 46),
    "mud": (86, 72, 52), "water": (46, 84, 150),
    "mountain": (104, 104, 116), "wall": (86, 86, 98),
    "gate": (120, 92, 60),
}
_TEAM = {"red": (206, 66, 66), "blue": (72, 116, 220),
         "green": (80, 170, 90), "gold": (210, 180, 70)}
_BG = (24, 24, 30)
_TICK_MS = 220                        # sim step cadence while playing


def _team_color(team: str) -> tuple:
    return _TEAM.get(team, (180, 180, 180))


class BattleScreen:
    def __init__(self, scenario_id: str, width: int = 1024,
                 height: int = 700, seed: int = 1):
        if not PYGAME_OK:
            raise RuntimeError("pygame not installed")
        pygame.init()
        pygame.display.set_caption("LLM-RPG — Battle Testbed")
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 15)
        self.big = pygame.font.SysFont("monospace", 30, bold=True)
        self.small = pygame.font.SysFont("monospace", 12)
        self.width, self.height = width, height
        self.scenario_id = scenario_id
        self.seed = seed
        self.view_h = height - 92          # leave a HUD strip at bottom
        self._reset()

    def _reset(self) -> None:
        self.field = build_field(self.scenario_id)
        self.session = BattleSession(self.field, seed=self.seed)
        self.cam = BattleCamera(self.field.width, self.field.height,
                                self.width, self.view_h,
                                tile_size=32)
        self.playing = True
        self._acc = 0

    # ------------------------------------------------------- loop

    def run(self) -> dict:
        """Block until the user backs out. Returns a small result."""
        while True:
            dt = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return {"action": "menu"}
                if event.type == pygame.KEYDOWN:
                    if self._key(event.key) == "exit":
                        return {"action": "menu",
                                "result": self.session.result()}
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self._wheel(event)
            if self.playing and not self.session.over():
                self._acc += dt
                while self._acc >= _TICK_MS:
                    self.session.tick()
                    self._acc -= _TICK_MS
            self._render()

    def _key(self, k) -> Optional[str]:
        if k in (pygame.K_ESCAPE, pygame.K_q):
            return "exit"
        if k == pygame.K_SPACE:
            self.playing = not self.playing
        elif k == pygame.K_n:
            if not self.session.over():
                self.session.tick()
        elif k == pygame.K_r:
            self._reset()
        elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.cam.zoom_in()
        elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.cam.zoom_out()
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.cam.pan(-3, 0)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.cam.pan(3, 0)
        elif k in (pygame.K_UP, pygame.K_w):
            self.cam.pan(0, -3)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.cam.pan(0, 3)
        return None

    def _wheel(self, event) -> None:
        if event.button == 4:
            self.cam.zoom_in()
        elif event.button == 5:
            self.cam.zoom_out()

    # ----------------------------------------------------- render

    def _render(self) -> None:
        self.screen.fill(_BG)
        self._draw_terrain()
        if self.cam.blob_mode:
            self._draw_blobs()
        else:
            self._draw_soldiers()
            self._draw_tracers()
        self._draw_hud()
        pygame.display.flip()

    def _draw_terrain(self) -> None:
        x0, y0, x1, y1 = self.cam.visible_tile_bounds()
        ts = self.cam.tile_size
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                kind = self.field.terrain[ty][tx]
                col = _TERRAIN.get(kind, _TERRAIN["grass"])
                sx, sy = self.cam.world_to_screen(tx, ty)
                rect = pygame.Rect(int(sx), int(sy), ts + 1, ts + 1)
                pygame.draw.rect(self.screen, col, rect)
                if ts >= 16 and kind in ("wall", "gate"):
                    pygame.draw.rect(self.screen, (40, 40, 48),
                                     rect, 1)

    def _draw_soldiers(self) -> None:
        ts = self.cam.tile_size
        r = max(2, ts // 2 - 1)
        for sq in self.field.squads.values():
            base = _team_color(sq.team)
            col = tuple(c // 2 for c in base) if sq.routed else base
            shape = category_shape(sq.category)
            for sol in sq.alive_soldiers:
                sx, sy = self.cam.world_to_screen(sol.x + 0.5,
                                                  sol.y + 0.5)
                if not (0 <= sx <= self.width and 0 <= sy <= self.view_h):
                    continue
                self._marker(shape, col, sx, sy, r)
                if sol.hp < sol.max_hp and ts >= 32:
                    self._hp_pip(sx, sy, r, sol)

    def _marker(self, shape, col, sx, sy, r) -> None:
        """Draw a unit-type glyph: team colour, category shape."""
        ix, iy = int(sx), int(sy)
        if shape == "circle":
            pygame.draw.circle(self.screen, col, (ix, iy), r)
        elif shape == "cross":                # medic: a plus
            t = max(1, r // 2)
            pygame.draw.rect(self.screen, col, (ix - r, iy - t, 2 * r, 2 * t))
            pygame.draw.rect(self.screen, col, (ix - t, iy - r, 2 * t, 2 * r))
        else:
            pts = marker_points(shape, sx, sy, r)
            pygame.draw.polygon(self.screen, col, pts)
        if r >= 5:                            # a thin rim reads the edge
            pygame.draw.circle(self.screen, (16, 16, 20), (ix, iy),
                               r + 1, 1)

    def _draw_tracers(self) -> None:
        """The ranged shots fired last tick, as fading arrow lines."""
        if self.cam.tile_size < 16:
            return
        for (x0, y0, x1, y1) in self.session.tracers:
            ax, ay = self.cam.world_to_screen(x0 + 0.5, y0 + 0.5)
            bx, by = self.cam.world_to_screen(x1 + 0.5, y1 + 0.5)
            pygame.draw.line(self.screen, (240, 226, 150),
                             (int(ax), int(ay)), (int(bx), int(by)), 1)
            pygame.draw.circle(self.screen, (250, 240, 180),
                               (int(bx), int(by)), 2)

    def _hp_pip(self, sx, sy, r, sol) -> None:
        frac = sol.hp / max(1, sol.max_hp)
        w = int(2 * r * frac)
        pygame.draw.rect(self.screen, (30, 30, 30),
                         (int(sx - r), int(sy - r - 4), 2 * r, 2))
        pygame.draw.rect(self.screen, (90, 210, 90),
                         (int(sx - r), int(sy - r - 4), w, 2))

    def _draw_blobs(self) -> None:
        """LOD: one circle per squad, sized by strength."""
        for sq in self.field.squads.values():
            c = sq.centroid()
            if c is None:
                continue
            base = _team_color(sq.team)
            col = tuple(x // 2 for x in base) if sq.routed else base
            sx, sy = self.cam.world_to_screen(c[0] + 0.5, c[1] + 0.5)
            r = max(4, int(3 + sq.strength ** 0.5 * 2))
            pygame.draw.circle(self.screen, col, (int(sx), int(sy)), r)
            pygame.draw.circle(self.screen, (12, 12, 16),
                               (int(sx), int(sy)), r, 1)
            label = self.small.render(str(sq.strength), True,
                                      (240, 240, 240))
            self.screen.blit(label, (int(sx) - label.get_width() // 2,
                                     int(sy) - 6))

    def _draw_hud(self) -> None:
        y = self.view_h + 2
        pygame.draw.rect(self.screen, (14, 14, 18),
                         (0, y, self.width, self.height - y))
        strengths = team_strengths(self.field)
        parts = [f"{t}:{n}" for t, n in strengths.items()]
        state = "PLAYING" if self.playing else "PAUSED"
        res = self.session.result()
        if self.session.over():
            state = f"OVER — {res['winner'] or 'draw'} wins"
        head = (f"{self.scenario_id}   tick {self.session.tick_count}"
                f"   {'  '.join(parts)}   [{state}]"
                f"   zoom {self.cam.tile_size}px"
                f"{'  (blobs)' if self.cam.blob_mode else ''}")
        self.screen.blit(self.font.render(head, True, (235, 235, 235)),
                         (12, y + 8))
        hint = ("SPACE play/pause  N step  R reset  +/- zoom  "
                "arrows/WASD pan  ESC back")
        self.screen.blit(self.small.render(hint, True, (150, 150, 160)),
                         (12, y + 34))
        # team strength bars
        bx = 12
        total = max(1, sum(strengths.values()))
        for t, n in strengths.items():
            w = int((self.width - 24) * n / total)
            pygame.draw.rect(self.screen, _team_color(t),
                             (bx, y + 56, w, 8))
            bx += w
        if self.session.over():
            self._banner(res)

    def _banner(self, res: dict) -> None:
        winner = res["winner"] or "draw"
        col = _team_color(winner) if res["winner"] else (200, 200, 200)
        txt = self.big.render(f"{winner.upper()} WINS", True, col)
        box = txt.get_rect(center=(self.width // 2, self.view_h // 2))
        bg = box.inflate(40, 24)
        s = pygame.Surface(bg.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, 170))
        self.screen.blit(s, bg.topleft)
        self.screen.blit(txt, box)


def run_battle_testbed(scenario_id: str, width: int = 1024,
                       height: int = 700, seed: int = 1) -> dict:
    """Entry point the start menu routes into. Returns a result dict."""
    return BattleScreen(scenario_id, width, height, seed).run()
