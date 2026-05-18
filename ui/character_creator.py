"""Character creator — multi-step flow for customizing the player.

Returns a `CharacterSpec` dict that `engine.demo_setup.create_default_player`
consumes to build the actual Character.

Steps:
1. Name (typed in)
2. Race (with stat bonuses)
3. Class (with starting inventory + symbol)
4. Stats (rolled 4d6 keep best 3, with re-roll option)
5. Confirm
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

from characters.character_types import CharacterClass, CharacterRace

logger = logging.getLogger("llm_rpg.creator")


# Race bonuses (str, dex, con, int, wis, cha)
RACE_BONUSES: Dict[CharacterRace, Tuple[int, int, int, int, int, int]] = {
    CharacterRace.HUMAN:     (1, 1, 1, 1, 1, 1),
    CharacterRace.ELF:       (0, 2, 0, 1, 0, 0),
    CharacterRace.DWARF:     (0, 0, 2, 0, 1, 0),
    CharacterRace.HALFLING:  (0, 2, 0, 0, 0, 1),
    CharacterRace.ORC:       (2, 0, 1, 0, 0, 0),
    CharacterRace.HALF_ORC:  (2, 0, 1, 0, 0, 0),
    CharacterRace.HALF_ELF:  (0, 1, 0, 0, 0, 2),
    CharacterRace.GNOME:     (0, 0, 0, 2, 1, 0),
    CharacterRace.TIEFLING:  (0, 0, 0, 1, 0, 2),
    CharacterRace.DRAGONBORN:(2, 0, 0, 0, 0, 1),
    CharacterRace.GOBLIN:    (0, 2, 0, 0, 0, 0),
    CharacterRace.TROLL:     (3, 0, 2, -1, -1, -1),
}

# Class starting inventory IDs and symbol
CLASS_STARTERS = {
    CharacterClass.WARRIOR:  (["sword", "shield", "potion"], "@"),
    CharacterClass.WIZARD:   (["staff", "spellbook", "potion"], "@"),
    CharacterClass.ROGUE:    (["dagger", "lockpicks", "potion"], "@"),
    CharacterClass.CLERIC:   (["holy_symbol", "bandage", "potion"], "@"),
    CharacterClass.BARD:     (["lute", "dagger", "ale"], "@"),
    CharacterClass.RANGER:   (["bow", "leather", "bandage"], "@"),
    CharacterClass.PALADIN:  (["longsword", "shield", "holy_symbol"], "@"),
    CharacterClass.MONK:     (["dagger", "bandage", "bandage"], "@"),
    CharacterClass.SORCERER: (["staff", "potion", "potion"], "@"),
    CharacterClass.WARLOCK:  (["staff", "spellbook"], "@"),
    CharacterClass.DRUID:    (["staff", "bandage", "herb_bundle"], "@"),
    CharacterClass.BARBARIAN:(["battleaxe", "leather", "ale"], "@"),
    CharacterClass.ARTIFICER:(["dagger", "spellbook"], "@"),
    CharacterClass.NOBLE:    (["dagger", "wine"], "@"),
    CharacterClass.VILLAGER: (["dagger", "bread"], "@"),
}


# Picklists used in the UI (filter out hostile classes/races)
PLAYER_RACES = [
    CharacterRace.HUMAN, CharacterRace.ELF, CharacterRace.DWARF,
    CharacterRace.HALFLING, CharacterRace.HALF_ELF, CharacterRace.HALF_ORC,
    CharacterRace.GNOME, CharacterRace.TIEFLING, CharacterRace.DRAGONBORN,
]
PLAYER_CLASSES = [
    CharacterClass.WARRIOR, CharacterClass.WIZARD, CharacterClass.ROGUE,
    CharacterClass.CLERIC, CharacterClass.BARD, CharacterClass.RANGER,
    CharacterClass.PALADIN, CharacterClass.MONK, CharacterClass.SORCERER,
    CharacterClass.WARLOCK, CharacterClass.DRUID, CharacterClass.BARBARIAN,
    CharacterClass.ARTIFICER, CharacterClass.NOBLE,
]


@dataclass
class CharacterSpec:
    name: str = "Player"
    race: CharacterRace = CharacterRace.HUMAN
    character_class: CharacterClass = CharacterClass.WARRIOR
    stats: Dict[str, int] = field(default_factory=lambda: {
        "strength": 10, "dexterity": 10, "constitution": 10,
        "intelligence": 10, "wisdom": 10, "charisma": 10,
    })

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "race": self.race.value,
            "class": self.character_class.value,
            "stats": dict(self.stats),
        }


def default_quick_start_spec() -> CharacterSpec:
    return CharacterSpec(
        name="Player",
        race=CharacterRace.HUMAN,
        character_class=CharacterClass.WARRIOR,
        stats={"strength": 14, "dexterity": 12, "constitution": 14,
               "intelligence": 10, "wisdom": 10, "charisma": 12},
    )


def roll_stats(rng: random.Random = None) -> Dict[str, int]:
    """4d6 drop lowest, classic D&D method."""
    rng = rng or random.Random()
    stats = {}
    for stat in ("strength", "dexterity", "constitution",
                 "intelligence", "wisdom", "charisma"):
        rolls = sorted(rng.randint(1, 6) for _ in range(4))
        stats[stat] = sum(rolls[1:])
    return stats


def apply_race_bonus(stats: Dict[str, int],
                     race: CharacterRace) -> Dict[str, int]:
    bonus = RACE_BONUSES.get(race, (0, 0, 0, 0, 0, 0))
    keys = ("strength", "dexterity", "constitution",
            "intelligence", "wisdom", "charisma")
    return {k: stats[k] + b for k, b in zip(keys, bonus)}


class CharacterCreator:
    """Pygame-based character creator screen."""

    STEPS = ("name", "race", "class", "stats", "confirm")

    def __init__(self, screen, font, big_font):
        if not PYGAME_OK:
            raise RuntimeError("pygame not installed")
        self.screen = screen
        self.font = font
        self.big_font = big_font
        self.step_idx = 0
        self.spec = CharacterSpec()
        self.spec.name = ""
        self.cursor = 0
        self.rolled_stats = roll_stats(random.Random())

    @property
    def step(self) -> str:
        return self.STEPS[self.step_idx]

    def handle_key(self, event) -> bool:
        """Return True when creator is finished (spec ready)."""
        k = event.key

        if self.step == "name":
            return self._name_key(event)
        if self.step == "race":
            return self._race_key(k)
        if self.step == "class":
            return self._class_key(k)
        if self.step == "stats":
            return self._stats_key(k)
        if self.step == "confirm":
            return self._confirm_key(k)
        return False

    # ---- name -------------------------------------------------------

    def _name_key(self, event) -> bool:
        k = event.key
        if k == pygame.K_RETURN:
            if not self.spec.name.strip():
                self.spec.name = "Adventurer"
            self.step_idx += 1
            self.cursor = 0
            return False
        if k == pygame.K_BACKSPACE:
            self.spec.name = self.spec.name[:-1]
            return False
        if k == pygame.K_ESCAPE:
            # Submit with current values
            return True
        ch = event.unicode
        if ch and ch.isprintable() and len(self.spec.name) < 18:
            self.spec.name += ch
        return False

    # ---- race -------------------------------------------------------

    def _race_key(self, k) -> bool:
        if k in (pygame.K_UP, pygame.K_w):
            self.cursor = (self.cursor - 1) % len(PLAYER_RACES)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.cursor = (self.cursor + 1) % len(PLAYER_RACES)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self.spec.race = PLAYER_RACES[self.cursor]
            self.step_idx += 1
            self.cursor = 0
        elif k == pygame.K_BACKSPACE:
            self.step_idx -= 1
        return False

    # ---- class ------------------------------------------------------

    def _class_key(self, k) -> bool:
        if k in (pygame.K_UP, pygame.K_w):
            self.cursor = (self.cursor - 1) % len(PLAYER_CLASSES)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.cursor = (self.cursor + 1) % len(PLAYER_CLASSES)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self.spec.character_class = PLAYER_CLASSES[self.cursor]
            self.step_idx += 1
            self.cursor = 0
        elif k == pygame.K_BACKSPACE:
            self.step_idx -= 1
        return False

    # ---- stats ------------------------------------------------------

    def _stats_key(self, k) -> bool:
        if k == pygame.K_r:
            self.rolled_stats = roll_stats(random.Random())
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self.spec.stats = apply_race_bonus(
                self.rolled_stats, self.spec.race)
            self.step_idx += 1
        elif k == pygame.K_BACKSPACE:
            self.step_idx -= 1
        return False

    # ---- confirm ----------------------------------------------------

    def _confirm_key(self, k) -> bool:
        if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_y):
            return True  # done
        if k == pygame.K_BACKSPACE:
            self.step_idx -= 1
        return False

    def build_spec(self) -> CharacterSpec:
        return self.spec

    # ---- rendering --------------------------------------------------

    def render(self) -> None:
        w, h = self.screen.get_size()
        title = self.big_font.render(
            f"Create Character — Step {self.step_idx+1}/5",
            True, (240, 220, 140))
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 40))

        if self.step == "name":
            self._render_name(w, h)
        elif self.step == "race":
            self._render_race(w, h)
        elif self.step == "class":
            self._render_class(w, h)
        elif self.step == "stats":
            self._render_stats(w, h)
        elif self.step == "confirm":
            self._render_confirm(w, h)

        hint = self.font.render(
            "Enter to confirm  ·  Backspace to go back  ·  Esc to finish",
            True, (130, 130, 150))
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, h - 36))

    def _render_name(self, w, h):
        prompt = self.font.render("Enter your character's name:",
                                  True, (200, 200, 220))
        self.screen.blit(prompt, (w // 2 - prompt.get_width() // 2, 200))
        box = pygame.Rect(w // 2 - 200, 240, 400, 36)
        pygame.draw.rect(self.screen, (30, 30, 50), box)
        pygame.draw.rect(self.screen, (200, 180, 100), box, 2)
        name = self.font.render(self.spec.name + "_", True, (255, 255, 255))
        self.screen.blit(name, (box.x + 10, box.y + 8))

    def _render_race(self, w, h):
        prompt = self.font.render("Choose your race:", True, (200, 200, 220))
        self.screen.blit(prompt, (200, 140))
        y = 180
        for i, race in enumerate(PLAYER_RACES):
            selected = i == self.cursor
            color = (255, 255, 255) if selected else (160, 160, 180)
            prefix = "> " if selected else "  "
            row = self.font.render(prefix + race.value, True, color)
            self.screen.blit(row, (240, y))
            if selected:
                bonus = RACE_BONUSES[race]
                stat_names = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
                bonus_text = "  ".join(
                    f"{name} {'+' if b >= 0 else ''}{b}"
                    for name, b in zip(stat_names, bonus) if b != 0)
                if bonus_text:
                    sub = self.font.render(
                        bonus_text, True, (200, 200, 130))
                    self.screen.blit(sub, (440, y))
            y += 28

    def _render_class(self, w, h):
        prompt = self.font.render("Choose your class:", True, (200, 200, 220))
        self.screen.blit(prompt, (200, 110))
        # Two columns
        col_height = 28 * len(PLAYER_CLASSES) // 2 + 100
        for i, cls in enumerate(PLAYER_CLASSES):
            selected = i == self.cursor
            color = (255, 255, 255) if selected else (160, 160, 180)
            prefix = "> " if selected else "  "
            row = self.font.render(prefix + cls.value, True, color)
            col = i % 2
            row_idx = i // 2
            x = 240 + col * 280
            y = 150 + row_idx * 28
            self.screen.blit(row, (x, y))
        # Description for currently-hovered class
        cls = PLAYER_CLASSES[self.cursor]
        starter, _ = CLASS_STARTERS.get(cls, ([], "@"))
        desc = self.font.render(
            f"Starting gear: {', '.join(starter)}",
            True, (200, 200, 130))
        self.screen.blit(desc, (240, 150 + col_height // 2 + 80))

    def _render_stats(self, w, h):
        prompt = self.font.render(
            "Rolled stats (4d6 drop lowest) — press R to re-roll, Enter to keep:",
            True, (200, 200, 220))
        self.screen.blit(prompt, (200, 140))
        y = 200
        race_bonus = RACE_BONUSES.get(self.spec.race, (0, 0, 0, 0, 0, 0))
        for i, stat in enumerate(("strength", "dexterity", "constitution",
                                  "intelligence", "wisdom", "charisma")):
            base = self.rolled_stats[stat]
            bonus = race_bonus[i]
            total = base + bonus
            mod = (total - 10) // 2
            text = f"{stat.upper()[:3]}  {base}" + \
                   (f" + {bonus} = {total}" if bonus else f" = {total}") + \
                   f"   (mod {'+' if mod >= 0 else ''}{mod})"
            row = self.font.render(text, True, (200, 200, 220))
            self.screen.blit(row, (260, y))
            y += 30

    def _render_confirm(self, w, h):
        race_bonus = RACE_BONUSES.get(self.spec.race, (0, 0, 0, 0, 0, 0))
        stats = apply_race_bonus(self.rolled_stats, self.spec.race)
        lines = [
            f"Name: {self.spec.name}",
            f"Race: {self.spec.race.value}",
            f"Class: {self.spec.character_class.value}",
            "",
            f"STR {stats['strength']}    DEX {stats['dexterity']}    CON {stats['constitution']}",
            f"INT {stats['intelligence']}    WIS {stats['wisdom']}    CHA {stats['charisma']}",
            "",
            "Press Enter to begin your adventure.",
        ]
        y = 180
        for line in lines:
            row = self.font.render(line, True, (220, 220, 240))
            self.screen.blit(row, (w // 2 - row.get_width() // 2, y))
            y += 28
