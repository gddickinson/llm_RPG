"""The unified Character Hub (GAP.6) — George's "one place" for the
player: a multi-tabbed window over Character, Equipment (a drag-and-drop
paper-doll + bags), Skills, Spells, Quests, Journal/History and Options.

Opened on C (upgrading the old text character-sheet). Mouse + keyboard:
click a tab or [ ] / Tab / 1-7 to switch, Esc or C to close. The content
builders (`ui/hub_data`) and the equipment geometry (`ui/hub_paperdoll`)
are pure; this controller wires them to the screen.
"""

try:
    import pygame
    PYGAME_OK = True
except ImportError:                       # pragma: no cover
    PYGAME_OK = False

from ui import hub_data
from ui import hub_paperdoll as doll

TABS = ["Character", "Equipment", "Skills", "Spells", "Training",
        "Quests", "Journal", "Options"]
_LINE_BUILDERS = {
    "Character": hub_data.character_lines,
    "Skills": hub_data.skills_lines,
    "Spells": hub_data.spells_lines,
    "Quests": hub_data.quests_lines,
    "Journal": hub_data.journal_lines,
}


class PlayerScreen:
    def __init__(self, gui):
        self.gui = gui
        self.tab = 0
        self.scroll = 0
        self.drag = None
        self.opt_cursor = 0
        self.train_cursor = 0
        self._f = self._big = self._small = None

    # ---- fonts / geometry --------------------------------------------

    def _fonts(self):
        if self._f is None and PYGAME_OK:
            pygame.font.init()
            self._f = pygame.font.SysFont("monospace", 15)
            self._big = pygame.font.SysFont("monospace", 22, bold=True)
            self._small = pygame.font.SysFont("monospace", 12)

    def _panel(self):
        W, H = self.gui.screen.get_size()
        m = max(24, min(48, W // 24))
        return pygame.Rect(m, m, W - 2 * m, H - 2 * m)

    def _tab_rects(self, panel):
        n = len(TABS)
        bw = panel.width // n
        y = panel.y + 8
        return [pygame.Rect(panel.x + i * bw, y, bw - 4, 30)
                for i in range(n)]

    def _body(self, panel):
        return pygame.Rect(panel.x + 16, panel.y + 52,
                           panel.width - 32, panel.height - 68)

    # ---- lifecycle ----------------------------------------------------

    def open(self):
        self.gui.mode = "player"

    def close(self):
        self.drag = None
        self.gui.mode = "play"

    # ---- input --------------------------------------------------------

    def handle_event(self, event):
        if not PYGAME_OK:
            return True
        panel = self._panel()
        if event.type == pygame.KEYDOWN:
            return self._key(event)
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y * 3)
            return True
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                          pygame.MOUSEMOTION):
            if event.type == pygame.MOUSEBUTTONDOWN and \
                    getattr(event, "button", 1) == 1:
                for i, r in enumerate(self._tab_rects(panel)):
                    if r.collidepoint(event.pos):
                        self._set_tab(i)
                        return True
            name = TABS[self.tab]
            if name == "Equipment":
                return doll.handle_event(event, self.gui, self,
                                         self._body(panel))
            if name == "Options" and \
                    event.type == pygame.MOUSEBUTTONDOWN:
                return self._options_click(event.pos, panel)
            if name == "Training" and \
                    event.type == pygame.MOUSEBUTTONDOWN:
                from ui import hub_training
                return hub_training.handle_click(event.pos,
                                                 self._body(panel),
                                                 self.gui, self)
        return True

    def _key(self, event):
        k = event.key
        if k in (pygame.K_ESCAPE, pygame.K_c):
            self.close()
            return True
        if k == pygame.K_TAB:
            shift = event.mod & pygame.KMOD_SHIFT
            self._set_tab((self.tab + (-1 if shift else 1)) % len(TABS))
            return True
        if k == pygame.K_RIGHTBRACKET:
            self._set_tab((self.tab + 1) % len(TABS))
            return True
        if k == pygame.K_LEFTBRACKET:
            self._set_tab((self.tab - 1) % len(TABS))
            return True
        if pygame.K_1 <= k <= pygame.K_8:
            self._set_tab(k - pygame.K_1)
            return True
        if TABS[self.tab] == "Options":
            return self._options_key(k)
        if TABS[self.tab] == "Training":
            from ui import hub_training
            return hub_training.handle_key(event, self.gui, self)
        if k in (pygame.K_DOWN, pygame.K_s):
            self.scroll += 2
        elif k in (pygame.K_UP, pygame.K_w):
            self.scroll = max(0, self.scroll - 2)
        elif k == pygame.K_i and TABS[self.tab] != "Equipment":
            self._set_tab(TABS.index("Equipment"))
        return True

    def _set_tab(self, i):
        self.tab = i % len(TABS)
        self.scroll = 0
        self.drag = None
        self.train_cursor = 0

    # ---- options tab --------------------------------------------------

    def _opt_rows(self):
        from engine import settings
        return settings.all_options()

    def _options_key(self, k):
        rows = self._opt_rows()
        if k in (pygame.K_DOWN, pygame.K_s):
            self.opt_cursor = (self.opt_cursor + 1) % len(rows)
        elif k in (pygame.K_UP, pygame.K_w):
            self.opt_cursor = (self.opt_cursor - 1) % len(rows)
        elif k in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_d):
            self._cycle_opt(rows[self.opt_cursor]["key"], 1)
        elif k in (pygame.K_LEFT, pygame.K_a):
            self._cycle_opt(rows[self.opt_cursor]["key"], -1)
        return True

    def _options_click(self, pos, panel):
        body = self._body(panel)
        rows = self._opt_rows()
        for i in range(len(rows)):
            ry = body.y + 40 + i * 26
            if ry <= pos[1] < ry + 26:
                self.opt_cursor = i
                self._cycle_opt(rows[i]["key"], 1)
                return True
        return True

    def _cycle_opt(self, key, step):
        from engine import settings
        from ui.settings_panel import apply_setting
        val = settings.cycle_setting(self.gui.engine.player, key, step)
        try:
            apply_setting(self.gui, key, val)
        except Exception:
            pass

    # ---- drawing ------------------------------------------------------

    def draw(self, target, _rect=None):
        if not PYGAME_OK:
            return
        self._fonts()
        panel = self._panel()
        overlay = pygame.Surface(panel.size, pygame.SRCALPHA)
        overlay.fill((14, 15, 22, 246))
        target.blit(overlay, panel.topleft)
        pygame.draw.rect(target, (120, 124, 150), panel, 1, border_radius=8)

        for i, r in enumerate(self._tab_rects(panel)):
            active = i == self.tab
            pygame.draw.rect(target, (44, 48, 66) if active else (24, 26, 36),
                             r, border_radius=5)
            if active:
                pygame.draw.rect(target, (150, 180, 240), r, 1,
                                 border_radius=5)
            col = (235, 235, 210) if active else (150, 152, 168)
            t = self._small.render(f"{i+1} {TABS[i]}", True, col)
            target.blit(t, (r.centerx - t.get_width() // 2, r.y + 8))

        body = self._body(panel)
        name = TABS[self.tab]
        if name == "Equipment":
            doll.draw_equipment(target, body, self.gui, self,
                                self._f, self._small)
        elif name == "Options":
            self._draw_options(target, body)
        elif name == "Training":
            from ui import hub_training
            hub_training.draw_training(target, body, self.gui, self,
                                       self._f, self._small, self._big)
        else:
            self._draw_lines(target, body, _LINE_BUILDERS[name])

        hint = self._small.render(
            "[ ] or Tab / 1-8 switch tab   ·   drag items to (un)equip   ·"
            "   Esc / C close", True, (150, 152, 168))
        target.blit(hint, (panel.centerx - hint.get_width() // 2,
                           panel.bottom - 22))

    def _draw_lines(self, target, body, builder):
        try:
            lines = builder(self.gui.engine)
        except Exception:
            lines = ["(unavailable)"]
        lh = self._f.get_height() + 3
        visible = body.height // lh
        self.scroll = max(0, min(self.scroll,
                                 max(0, len(lines) - visible)))
        y = body.y
        for line in lines[self.scroll:self.scroll + visible]:
            header = line and (line.isupper() or line.endswith(":")) \
                and not line.startswith("  ")
            col = (240, 220, 140) if header else (210, 212, 210)
            target.blit(self._f.render(line, True, col), (body.x, y))
            y += lh
        if len(lines) > visible:
            more = self._small.render(
                f"  scroll ↑/↓  ({self.scroll+1}-"
                f"{min(self.scroll+visible, len(lines))} of {len(lines)})",
                True, (140, 142, 158))
            target.blit(more, (body.x, body.bottom - 16))

    def _draw_options(self, target, body):
        from engine import settings
        title = self._big.render("Options", True, (240, 220, 140))
        target.blit(title, (body.x, body.y))
        rows = self._opt_rows()
        for i, o in enumerate(rows):
            y = body.y + 40 + i * 26
            val = settings.get_setting(self.gui.engine.player, o["key"])
            sel = i == self.opt_cursor
            if sel:
                pygame.draw.rect(target, (40, 44, 60),
                                 (body.x - 4, y - 3, 360, 24),
                                 border_radius=4)
            col = (235, 235, 210) if sel else (200, 200, 190)
            target.blit(self._f.render(f"{o['label']:<18}", True, col),
                        (body.x, y))
            target.blit(self._f.render(f"< {val} >", True,
                                       (150, 200, 250) if sel else col),
                        (body.x + 230, y))
