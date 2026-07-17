"""Start menu — title screen with New Game / Load / Quit.

This screen is shown by `main.py` before constructing the GameEngine.
It returns a dict describing the user's choice:
    {"action": "new", "spec": <CharacterSpec or None>}
    {"action": "load", "save_name": "..."}
    {"action": "quit"}
"""

import logging
import os
from typing import Optional

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

import config
from ui.character_creator import CharacterCreator, default_quick_start_spec

logger = logging.getLogger("llm_rpg.start_menu")


# Menu state machine ----------------------------------------------------
TITLE_OPTIONS = [
    ("New Game", "new"),
    ("Load Game", "load"),
    ("Combat Arena", "arena"),                 # the colosseum — watch a matchup
    ("Battle Testbed", "battle"),
    ("Quit", "quit"),
]

NEW_GAME_OPTIONS = [
    ("Quick Start", "quick"),
    ("Tutorial Island", "tutorial"),           # A-disc: learn every system
    ("Customize Character", "customize"),
    ("Realistic World", "realistic"),          # P36.1 heightmap landscape
    ("Large Town (Oakvale)", "oakvale"),       # OAKVALE the big walled town
    ("Begin at the Castle", "castle"),
    ("Back", "back"),
]


class StartMenu:
    """Pygame-based start menu loop. Standalone — does not require an engine."""

    def __init__(self, width: int = 1024, height: int = 700,
                 save_dir: Optional[str] = None):
        if not PYGAME_OK:
            raise RuntimeError("pygame not installed")
        pygame.init()
        pygame.display.set_caption("LLM-RPG — Main Menu")
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 18)
        self.big_font = pygame.font.SysFont("monospace", 32, bold=True)
        self.sub_font = pygame.font.SysFont("monospace", 14)
        self.width = width
        self.height = height
        self.state = "title"
        self.selected = 0
        self.save_dir = save_dir or config.SAVE_DIRECTORY
        self.saves = []
        self.scenarios = []
        self.matchups = []                 # colosseum matchups (Combat Arena)
        self.creator: Optional[CharacterCreator] = None
        self.pending_start = "default"     # "castle" for the P18.5 start

    # ------------------------------------------------------------- main

    def run(self) -> dict:
        """Block until the user picks an action. Returns the action dict."""
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return {"action": "quit"}
                if event.type == pygame.KEYDOWN:
                    result = self._handle_key(event)
                    if result:
                        return result
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self._handle_click(event.pos)
                    if result:
                        return result
            self._render()
            self.clock.tick(30)

    # --------------------------------------------------------- input

    def _handle_key(self, event) -> Optional[dict]:
        k = event.key

        if self.state == "title":
            return self._title_key(k)

        if self.state == "new_game":
            return self._newgame_key(k)

        if self.state == "load_menu":
            return self._load_key(k)

        if self.state == "battle_menu":
            return self._battle_key(k)

        if self.state == "arena_menu":
            return self._arena_key(k)

        if self.state == "customize":
            done = self.creator.handle_key(event)
            if done:
                spec = self.creator.build_spec()
                self.creator = None
                start, self.pending_start = self.pending_start, "default"
                return {"action": "new", "spec": spec, "start": start}
            return None
        return None

    def _title_key(self, k) -> Optional[dict]:
        if k in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(TITLE_OPTIONS)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(TITLE_OPTIONS)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            return self._pick_title()
        elif k == pygame.K_ESCAPE:
            return {"action": "quit"}
        return None

    def _newgame_key(self, k) -> Optional[dict]:
        if k in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(NEW_GAME_OPTIONS)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(NEW_GAME_OPTIONS)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            label, code = NEW_GAME_OPTIONS[self.selected]
            if code == "quick":
                return {"action": "new", "spec": default_quick_start_spec(),
                        "start": "default"}
            if code == "realistic":            # P36.1 a heightmap-generated world
                return {"action": "new", "spec": default_quick_start_spec(),
                        "start": "realistic"}
            if code == "tutorial":             # A-disc: Tutorial Island start
                return {"action": "new", "spec": default_quick_start_spec(),
                        "start": "tutorial"}
            if code == "oakvale":              # OAKVALE the large walled town
                return {"action": "new", "spec": default_quick_start_spec(),
                        "start": "oakvale"}
            if code in ("customize", "castle"):
                # both make a hero; the castle option starts them at the gate
                self.pending_start = "castle" if code == "castle" \
                    else "default"
                self.creator = CharacterCreator(
                    self.screen, self.font, self.big_font)
                self.state = "customize"
                return None
            if code == "back":
                self.state = "title"
                self.selected = 0
                return None
        elif k == pygame.K_ESCAPE:
            self.state = "title"
            self.selected = 0
        return None

    def _load_key(self, k) -> Optional[dict]:
        if not self.saves:
            if k == pygame.K_ESCAPE:
                self.state = "title"
                self.selected = 0
            return None
        if k in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(self.saves)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(self.saves)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            name = self.saves[self.selected]["filename"]
            return {"action": "load", "save_name": name}
        elif k == pygame.K_ESCAPE:
            self.state = "title"
            self.selected = 0
        return None

    def _battle_key(self, k) -> Optional[dict]:
        if not self.scenarios:
            if k == pygame.K_ESCAPE:
                self.state = "title"
                self.selected = 0
            return None
        n = len(self.scenarios)
        _, rows, _, _ = self._grid_dims()
        if k in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % n
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % n
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.selected = (self.selected - rows) % n    # jump a column
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.selected = (self.selected + rows) % n
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            sid = self.scenarios[self.selected][0]
            return {"action": "battle", "scenario": sid}
        elif k == pygame.K_ESCAPE:
            self.state = "title"
            self.selected = 0
        return None

    def _arena_key(self, k) -> Optional[dict]:
        if not self.matchups:
            if k == pygame.K_ESCAPE:
                self.state = "title"
                self.selected = 0
            return None
        n = len(self.matchups)
        if k in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % n
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % n
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            mid = self.matchups[self.selected][0]
            # a Combat Arena fight seats a default hero as spectator in a normal
            # world and stages the matchup at the arena gate (main.py stages it)
            return {"action": "arena", "matchup": mid,
                    "spec": default_quick_start_spec(), "start": "default"}
        elif k == pygame.K_ESCAPE:
            self.state = "title"
            self.selected = 0
        return None

    def _pick_title(self) -> Optional[dict]:
        label, code = TITLE_OPTIONS[self.selected]
        if code == "new":
            self.state = "new_game"
            self.selected = 0
            return None
        if code == "load":
            self._refresh_saves()
            self.state = "load_menu"
            self.selected = 0
            return None
        if code == "battle":
            self._refresh_scenarios()
            self.state = "battle_menu"
            self.selected = 0
            return None
        if code == "arena":
            self._refresh_matchups()
            self.state = "arena_menu"
            self.selected = 0
            return None
        if code == "quit":
            return {"action": "quit"}
        return None

    def _handle_click(self, pos) -> Optional[dict]:
        # Mouse support is minimal — clicks behave like enter on the
        # currently-hovered item. Skipped for brevity.
        return None

    def _refresh_saves(self) -> None:
        from engine.save_load import SaveManager
        self.saves = SaveManager(self.save_dir).list_saves()

    def _refresh_scenarios(self) -> None:
        from engine.battle.battle_scenario import list_scenarios
        self.scenarios = list_scenarios()

    def _refresh_matchups(self) -> None:
        from engine.colosseum import list_matchups
        self.matchups = list_matchups()

    # --------------------------------------------------------- render

    def _render(self) -> None:
        self.screen.fill((10, 10, 20))
        if self.state == "title":
            self._render_menu("LLM-RPG", TITLE_OPTIONS,
                              "Use Arrows / Enter to select  ·  Esc to quit")
        elif self.state == "new_game":
            self._render_menu("New Game", NEW_GAME_OPTIONS,
                              "Quick Start uses a default warrior")
        elif self.state == "load_menu":
            self._render_save_list()
        elif self.state == "battle_menu":
            self._render_scenario_list()
        elif self.state == "arena_menu":
            self._render_arena_list()
        elif self.state == "customize" and self.creator:
            self.creator.render()
        pygame.display.flip()

    def _render_menu(self, title: str, options, hint: str) -> None:
        # Title
        title_surf = self.big_font.render(title, True, (240, 220, 140))
        self.screen.blit(
            title_surf,
            (self.width // 2 - title_surf.get_width() // 2, 110),
        )

        # Subtitle
        sub_surf = self.sub_font.render(
            "A locally-runnable D&D-style RPG",
            True, (170, 170, 200))
        self.screen.blit(
            sub_surf,
            (self.width // 2 - sub_surf.get_width() // 2, 160),
        )

        # Options
        y = 260
        for i, (label, _code) in enumerate(options):
            selected = (i == self.selected)
            color = (255, 255, 255) if selected else (160, 160, 180)
            text = ("> " if selected else "  ") + label + \
                   ("  <" if selected else "   ")
            surf = self.font.render(text, True, color)
            self.screen.blit(
                surf,
                (self.width // 2 - surf.get_width() // 2, y),
            )
            y += 36

        # Hint
        if hint:
            hint_surf = self.sub_font.render(hint, True, (130, 130, 150))
            self.screen.blit(
                hint_surf,
                (self.width // 2 - hint_surf.get_width() // 2,
                 self.height - 40),
            )

    def _render_save_list(self) -> None:
        title_surf = self.big_font.render("Load Game", True, (240, 220, 140))
        self.screen.blit(
            title_surf,
            (self.width // 2 - title_surf.get_width() // 2, 80),
        )

        if not self.saves:
            msg = self.font.render(
                "No saves found. Press Esc to go back.",
                True, (200, 160, 160))
            self.screen.blit(
                msg,
                (self.width // 2 - msg.get_width() // 2, 250),
            )
            return

        y = 180
        for i, save in enumerate(self.saves):
            selected = (i == self.selected)
            color = (255, 255, 255) if selected else (160, 160, 180)
            label = save["filename"]
            if save.get("label"):
                label += f" — {save['label']}"
            text = ("> " if selected else "  ") + label
            surf = self.font.render(text, True, color)
            self.screen.blit(surf, (180, y))
            y += 28
            if y > self.height - 80:
                break

        hint = self.sub_font.render(
            "Enter to load  ·  Esc to go back", True, (130, 130, 150))
        self.screen.blit(
            hint, (self.width // 2 - hint.get_width() // 2, self.height - 40))

    def _grid_dims(self):
        """(columns, rows-per-column, row-height, top-y) for the scenario
        grid — sized so every battle fits the page (P17: the list grew
        past a single scrollless column)."""
        top = 165
        bottom = self.height - 96
        row_h = 32
        rows = max(1, (bottom - top) // row_h)
        n = max(1, len(self.scenarios))
        cols = min(3, -(-n // rows))          # ceil; up to 3 columns
        return cols, rows, row_h, top

    def _render_scenario_list(self) -> None:
        title_surf = self.big_font.render(
            "Battle Testbed", True, (240, 220, 140))
        self.screen.blit(
            title_surf,
            (self.width // 2 - title_surf.get_width() // 2, 70))
        sub = self.sub_font.render(
            "Watch the tactical layer fight a staged battle",
            True, (170, 170, 200))
        self.screen.blit(
            sub, (self.width // 2 - sub.get_width() // 2, 118))

        cols, rows, row_h, top = self._grid_dims()
        col_w = (self.width - 200) // cols
        for i, (sid, name, desc) in enumerate(self.scenarios):
            col, row = i // rows, i % rows
            if col >= cols:                    # safety: never draw off-grid
                continue
            selected = (i == self.selected)
            color = (255, 255, 120) if selected else (175, 175, 195)
            text = ("> " if selected else "  ") + name
            surf = self.font.render(text, True, color)
            self.screen.blit(surf, (110 + col * col_w, top + row * row_h))

        # the selected battle's blurb, pinned below the grid so it never
        # collides with a row
        if self.scenarios:
            _, name, desc = self.scenarios[self.selected]
            nsurf = self.font.render(name, True, (240, 230, 160))
            self.screen.blit(
                nsurf, (self.width // 2 - nsurf.get_width() // 2,
                        self.height - 78))
            dsurf = self.sub_font.render(desc, True, (150, 175, 150))
            self.screen.blit(
                dsurf, (self.width // 2 - dsurf.get_width() // 2,
                        self.height - 56))

        hint = self.sub_font.render(
            "Arrows move  ·  Enter to fight  ·  Esc to go back",
            True, (130, 130, 150))
        self.screen.blit(
            hint, (self.width // 2 - hint.get_width() // 2,
                   self.height - 32))

    def _render_arena_list(self) -> None:
        title_surf = self.big_font.render(
            "Combat Arena", True, (240, 220, 140))
        self.screen.blit(
            title_surf, (self.width // 2 - title_surf.get_width() // 2, 80))
        sub = self.sub_font.render(
            "Watch real fighters brawl with full combat + graphics",
            True, (170, 170, 200))
        self.screen.blit(sub, (self.width // 2 - sub.get_width() // 2, 128))

        if not self.matchups:
            msg = self.font.render("No matchups found. Press Esc to go back.",
                                   True, (200, 160, 160))
            self.screen.blit(msg, (self.width // 2 - msg.get_width() // 2, 250))
            return

        y = 200
        for i, (_mid, name, _desc) in enumerate(self.matchups):
            selected = (i == self.selected)
            color = (255, 255, 120) if selected else (175, 175, 195)
            text = ("> " if selected else "  ") + name
            surf = self.font.render(text, True, color)
            self.screen.blit(
                surf, (self.width // 2 - surf.get_width() // 2, y))
            y += 34

        # the selected matchup's blurb, pinned below the list
        _mid, name, desc = self.matchups[self.selected]
        dsurf = self.sub_font.render(desc, True, (150, 175, 150))
        self.screen.blit(
            dsurf, (self.width // 2 - dsurf.get_width() // 2, self.height - 62))
        hint = self.sub_font.render(
            "Arrows move  ·  Enter to watch  ·  Esc to go back",
            True, (130, 130, 150))
        self.screen.blit(
            hint, (self.width // 2 - hint.get_width() // 2, self.height - 34))
