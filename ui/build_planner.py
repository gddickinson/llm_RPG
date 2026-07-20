"""M5 — the player BUILD / TERRAFORM planner: a plan-and-implement pop-up over
the live map (George: "specialized pop-up windows that allow them to plan and
implement their changes to the world, which persist").

A cursor moves over the ground near the hero (within `REACH`); the player paints
tiles from a brush palette into a PLAN (ghost preview), then COMMITS the whole
plan through the M0 `worldcraft` ruleset — so every placement obeys the same
skill/tool/resource/protected-ground rules a mason does, and the result persists
for free (the map snapshot). Draws over the still-rendered map (the GUI renders
the world in every mode), so it reads as an in-world editor, not a modal box.
"""

REACH = 6              # how far from the hero you may shape

try:
    import pygame
    PYGAME_OK = True
except Exception:                                    # pragma: no cover
    PYGAME_OK = False

# brush -> (target terrain, label). Only LABOUR-buildable terrains — growing a
# forest or conjuring water is instant CREATION and takes a spell (Plant Growth /
# Conjure Water), not a shovel, so those aren't build-tool brushes (George).
BRUSHES = [
    ("grass", "Level/Clear"), ("farmland", "Till"), ("road", "Road"),
    ("building", "Wall"), ("rubble", "Demolish"),
]
_GHOST = {
    "grass": (110, 170, 90), "farmland": (150, 120, 70),
    "road": (150, 140, 120), "building": (120, 120, 130),
    "rubble": (110, 100, 95),
}


def open_planner(gui) -> None:
    """Open the build/terraform tool on `gui` — outdoors only (worldcraft shapes
    the open world; interiors keep their own coordinate space)."""
    eng = gui.engine
    if getattr(eng, "current_dungeon", None) or \
            getattr(eng, "current_interior", None):
        eng.memory_manager.add_event(
            "You can only reshape the open land, not indoors.")
        return
    gui.build_planner = gui.build_planner or BuildPlanner(eng)
    gui.build_planner.open()
    gui.mode = "build"


class BuildPlanner:
    def __init__(self, engine):
        self.engine = engine
        self.cx, self.cy = tuple(engine.player.position)
        self.brush = 0
        self.plan = {}          # (x, y) -> terrain name (pending)
        self._bp_index = 0      # M6 which saved design to load next
        self._flash = ""        # a transient status line for the HUD

    def open(self) -> None:
        self.cx, self.cy = tuple(self.engine.player.position)

    # ---------------- input -----------------------------------------

    def _move(self, dx: int, dy: int) -> None:
        px, py = self.engine.player.position
        nx, ny = self.cx + dx, self.cy + dy
        wmap = self.engine.world.map
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            return
        if abs(nx - px) > REACH or abs(ny - py) > REACH:
            return
        self.cx, self.cy = nx, ny

    def handle_key(self, event) -> bool:
        if not PYGAME_OK or event.type != pygame.KEYDOWN:
            return False
        k = event.key
        if k in (pygame.K_LEFT, pygame.K_a):
            self._move(-1, 0)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self._move(1, 0)
        elif k in (pygame.K_UP, pygame.K_w):
            self._move(0, -1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self._move(0, 1)
        elif k in (pygame.K_LEFTBRACKET, pygame.K_q):
            self.brush = (self.brush - 1) % len(BRUSHES)
        elif k in (pygame.K_RIGHTBRACKET, pygame.K_e):
            self.brush = (self.brush + 1) % len(BRUSHES)
        elif pygame.K_1 <= k <= pygame.K_9:
            i = k - pygame.K_1
            if i < len(BRUSHES):
                self.brush = i
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self.plan[(self.cx, self.cy)] = BRUSHES[self.brush][0]
        elif k == pygame.K_x:
            self.plan.pop((self.cx, self.cy), None)
        elif k in (pygame.K_c, pygame.K_TAB):
            self._commit()
        elif k == pygame.K_v:               # M6 save the plan as a blueprint
            self._save_blueprint()
        elif k == pygame.K_l:               # M6 load the next saved design here
            self._load_blueprint()
        return True

    def _save_blueprint(self) -> None:
        from engine import blueprint_library as bl
        date = str(getattr(self.engine.world, "date", "") or "")
        msg = bl.save_blueprint(f"Design {bl.count() + 1}", self.plan, date)
        try:
            self.engine.memory_manager.add_event(f"[Build] {msg}")
        except Exception:
            pass

    def _load_blueprint(self) -> None:
        from engine import blueprint_library as bl
        designs = bl.list_blueprints()
        if not designs:
            self._flash = "No saved designs — plan tiles and press V to save one."
            return
        _bid, name, spec = designs[self._bp_index % len(designs)]
        self._bp_index += 1
        self.plan = bl.stamp(spec, self.cx, self.cy)   # ghost it at the cursor
        self._flash = f"Loaded '{name}' — move to position, then C to build."

    def _commit(self) -> None:
        from engine import worldcraft
        applied, refused = 0, 0
        for (x, y), to in list(self.plan.items()):
            ok, _ = worldcraft.mutate(self.engine, x, y, to, "labor",
                                      actor=self.engine.player, quiet=True)
            applied += 1 if ok else 0
            refused += 0 if ok else 1
        self.plan.clear()
        msg = f"[Build] You reshape the land — {applied} tiles set"
        if refused:
            msg += f", {refused} refused (skill / stone / protected)"
        msg += "."
        try:
            self.engine.memory_manager.add_event(msg)
        except Exception:
            pass

    # ---------------- render ----------------------------------------

    def _camera(self, view_rect, ts):
        wmap = self.engine.world.map
        px, py = self.engine.player.position
        cols, rows = view_rect.width // ts, view_rect.height // ts
        cam_x = max(0, min(wmap.width - cols, px - cols // 2))
        cam_y = max(0, min(wmap.height - rows, py - rows // 2))
        return cam_x, cam_y

    def draw(self, target, view_rect, ts) -> None:
        if not PYGAME_OK:
            return
        from engine import worldcraft
        cam_x, cam_y = self._camera(view_rect, ts)

        def scr(x, y):
            return (view_rect.x + (x - cam_x) * ts,
                    view_rect.y + (y - cam_y) * ts)

        # planned tiles as translucent ghosts
        for (x, y), to in self.plan.items():
            sx, sy = scr(x, y)
            ov = pygame.Surface((ts, ts), pygame.SRCALPHA)
            ov.fill((*_GHOST.get(to, (200, 200, 200)), 120))
            target.blit(ov, (sx, sy))
            pygame.draw.rect(target, (255, 255, 255), (sx, sy, ts, ts), 1)

        # the cursor, tinted by whether the current brush is legal here
        to = BRUSHES[self.brush][0]
        ok, why = worldcraft.can_mutate(self.engine, self.cx, self.cy, to,
                                        "labor", actor=self.engine.player)
        sx, sy = scr(self.cx, self.cy)
        col = (90, 220, 120) if ok else (230, 90, 90)
        pygame.draw.rect(target, col, (sx, sy, ts, ts), 3)

        self._hud(target, view_rect, to, ok, why)

    def _hud(self, target, view_rect, to, ok, why) -> None:
        font = pygame.font.SysFont("dejavusans", 15)
        small = pygame.font.SysFont("dejavusans", 12)
        bar = pygame.Rect(view_rect.x, view_rect.bottom - 66,
                          view_rect.width, 66)
        s = pygame.Surface(bar.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 220))
        target.blit(s, bar.topleft)
        pygame.draw.rect(target, (200, 180, 100), bar, 1)
        # brush palette
        x = bar.x + 10
        for i, (t, label) in enumerate(BRUSHES):
            sel = i == self.brush
            c = (255, 240, 160) if sel else (170, 170, 185)
            txt = small.render(f"{i + 1}.{label}", True, c)
            if sel:
                pygame.draw.rect(target, (255, 240, 160),
                                 (x - 3, bar.y + 6, txt.get_width() + 6, 18), 1)
            target.blit(txt, (x, bar.y + 8))
            x += txt.get_width() + 16
        # status + hints
        status = (f"Build here: {BRUSHES[self.brush][1]}" if ok
                  else f"Can't: {why}")
        target.blit(font.render(status, True,
                                (150, 230, 160) if ok else (235, 150, 150)),
                    (bar.x + 10, bar.y + 30))
        if self._flash:
            target.blit(small.render(self._flash, True, (200, 200, 130)),
                        (bar.x + 320, bar.y + 30))
        try:
            from engine import blueprint_library as bl
            saved = bl.count()
        except Exception:
            saved = 0
        hint = ("arrows move · [ ]/QE brush · 1-5 pick · Enter place · X erase · "
                f"C build · V save · L load ({saved} designs) · Esc close · "
                f"planned: {len(self.plan)}")
        target.blit(small.render(hint, True, (150, 150, 170)),
                    (bar.x + 10, bar.y + 48))
