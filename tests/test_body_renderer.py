"""Tests for the procedural body renderer (state + draw smoke)."""

import os
import math
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()


from ui.body_renderer import (
    _race_color, _race_scale, _class_color, _ensure_anim, update_anim,
    draw_body, draw_projectile, SKIN_TONES, CLASS_TORSO_TINT, RACE_SCALE,
    CLASS_WEAPON,
)
from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace


def _new_char():
    return Character(
        id="t", name="Tester",
        character_class=CharacterClass.WARRIOR, race=CharacterRace.HUMAN,
        level=1, strength=12, dexterity=12, constitution=12,
        intelligence=10, wisdom=10, charisma=10,
        hp=20, max_hp=20, position=(5, 5),
    )


class TestBodyRenderer(unittest.TestCase):
    def test_palettes_complete(self):
        for race in ("human", "elf", "dwarf", "halfling", "orc"):
            self.assertIn(race, SKIN_TONES)
        for klass in ("warrior", "wizard", "rogue"):
            self.assertIn(klass, CLASS_TORSO_TINT)

    def test_race_scale_known(self):
        self.assertAlmostEqual(_race_scale("human"), 1.0)
        self.assertLess(_race_scale("halfling"), 1.0)
        self.assertGreater(_race_scale("troll"), 1.0)

    def test_ensure_anim_creates_state(self):
        c = _new_char()
        anim = _ensure_anim(c)
        self.assertIn("walk_phase", anim)
        self.assertEqual(anim["prev_pos"], c.position)

    def test_walk_phase_advances_on_move(self):
        c = _new_char()
        _ensure_anim(c)
        update_anim(c, 0.1)
        c.position = (6, 5)
        update_anim(c, 0.1)
        self.assertGreater(c.metadata["_anim"]["walk_phase"], 0)
        self.assertTrue(c.metadata["_anim"]["moving"])

    def test_draw_does_not_crash(self):
        c = _new_char()
        surf = pygame.Surface((64, 64))
        # Should not raise
        draw_body(surf, c, 0, 0, 32, is_player=True)
        # Dead character drawing
        c.hp = 0
        c.status = "defeated"
        draw_body(surf, c, 0, 0, 32, is_player=False)

    def test_draw_projectile_kinds(self):
        surf = pygame.Surface((64, 64))
        for kind in ("arrow", "bolt", "stone", "spell", "unknown"):
            draw_projectile(surf, kind, 0, 0, 32)

    def test_class_weapon_table_complete(self):
        # Every class in the torso tint should appear in weapon table
        # (with possibly None for unarmed)
        for klass in CLASS_TORSO_TINT:
            self.assertIn(klass, CLASS_WEAPON)


if __name__ == "__main__":
    unittest.main()
