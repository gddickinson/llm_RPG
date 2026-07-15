"""Tests for combat visual effects (state-only; pygame draw not invoked)."""

import os
import unittest

# Headless pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()


from ui.combat_effects import (
    CombatEffects, DamagePopup, HitFlash, DeathEffect, Particle,
    SPELL_PARTICLE_COLORS,
)


class FakeChar:
    def __init__(self, id="t", x=0, y=0):
        self.id = id
        self.position = (x, y)


class FakeEngine:
    pass


class TestCombatEffects(unittest.TestCase):
    def setUp(self):
        self.ce = CombatEffects(FakeEngine())

    def test_spawn_damage_popup(self):
        self.ce.spawn_damage_popup(5, 5, 12)
        self.assertEqual(len(self.ce.damage_popups), 1)
        p = self.ce.damage_popups[0]
        self.assertEqual(p.value, 12)

    def test_hit_flash_dedups(self):
        c = FakeChar(id="x")
        self.ce.spawn_hit_flash(c)
        self.ce.spawn_hit_flash(c)
        self.assertEqual(len(self.ce.hit_flashes), 1)

    def test_death_effect_particles(self):
        self.ce.spawn_death_effect(3, 4)
        self.assertEqual(len(self.ce.death_effects), 1)
        de = self.ce.death_effects[0]
        self.assertEqual(len(de.particles), 5)

    def test_spell_burst(self):
        self.ce.spawn_spell_burst("fireball", 1, 1)
        self.assertGreater(len(self.ce.particles), 0)
        # Color of the first particle should be in fireball palette
        colors = SPELL_PARTICLE_COLORS["fireball"]
        self.assertIn(self.ce.particles[0].color, colors)

    def test_spell_burst_unknown(self):
        # Unknown spell falls back to magic_missile palette without crash
        self.ce.spawn_spell_burst("nonsense", 0, 0)
        self.assertGreater(len(self.ce.particles), 0)

    def test_on_damage_dealt_spawns_three(self):
        c = FakeChar()
        self.ce.on_damage_dealt(c, 7, is_kill=False)
        self.assertEqual(len(self.ce.damage_popups), 1)
        self.assertEqual(len(self.ce.hit_flashes), 1)
        self.assertEqual(len(self.ce.death_effects), 0)

    def test_on_damage_dealt_kill(self):
        c = FakeChar()
        self.ce.on_damage_dealt(c, 7, is_kill=True)
        self.assertEqual(len(self.ce.death_effects), 1)

    def test_on_heal_green_popup(self):
        c = FakeChar()
        self.ce.on_heal(c, 6)
        self.assertEqual(len(self.ce.damage_popups), 1)
        self.assertEqual(self.ce.damage_popups[0].color[1], 220)

    def test_update_expires(self):
        self.ce.spawn_damage_popup(0, 0, 1)
        # Tick past max_age
        self.ce.update(2.0)
        self.assertEqual(len(self.ce.damage_popups), 0)


class TestProjectionAgnosticDraw(unittest.TestCase):
    """P41.12 — draw_with lets the iso renderer reuse the same effect logic."""

    def setUp(self):
        self.ce = CombatEffects(FakeEngine())

    def _paint_count(self, surf, box):
        x0, y0, x1, y1 = box
        return sum(1 for x in range(x0, x1, 2) for y in range(y0, y1, 2)
                   if surf.get_at((x, y))[:3] != (0, 0, 0))

    def test_draw_with_custom_projection_paints(self):
        # a death burst (shapes, no font) routed through a custom to_screen that
        # maps every world point to the view centre → paints there
        self.ce.spawn_death_effect(5, 5)
        self.ce.update(0.05)
        surf = pygame.Surface((200, 200))
        surf.fill((0, 0, 0))
        view = pygame.Rect(0, 0, 200, 200)
        self.ce.draw_with(surf, view, lambda x, y: (100, 100), 32)
        self.assertGreater(self._paint_count(surf, (70, 70, 130, 130)), 0)

    def test_topdown_draw_delegates_to_draw_with(self):
        # the top-down draw still works after the refactor (a hit flash circle)
        self.ce.spawn_death_effect(2, 2)
        self.ce.update(0.05)
        surf = pygame.Surface((200, 200))
        surf.fill((0, 0, 0))
        view = pygame.Rect(0, 0, 200, 200)
        # cam at origin, ts 32 → world (2,2) maps near (80, 80)
        self.ce.draw(surf, view, 0, 0, 32)
        self.assertGreater(self._paint_count(surf, (0, 0, 200, 200)), 0)


if __name__ == "__main__":
    unittest.main()
