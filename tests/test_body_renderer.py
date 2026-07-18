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

    def test_head_does_not_smear_across_camera_jumps(self):
        """Regression (P34.3): the head/weapon springs run in body-LOCAL space,
        so a camera pan or a move BETWEEN LOCATIONS (a big jump in the on-screen
        sx) never drags the head away from the body. The stored spring offset
        must stay local (~0), not go absolute and chase sx."""
        c = _new_char()
        ts = 48
        surf = pygame.Surface((64, 64 * 4))
        for _ in range(6):                      # settle at the origin
            update_anim(c, 1 / 30.0)
            draw_body(surf, c, 0, 0, ts, is_player=False)
        near = c.metadata["_anim"]["_sec"]["head"][0]
        for _ in range(6):                      # camera jumps 2000px away
            update_anim(c, 1 / 30.0)
            draw_body(surf, c, 2000, 0, ts, is_player=False)
        far = c.metadata["_anim"]["_sec"]["head"][0]
        H = int(ts * 1.5)
        self.assertLess(abs(near), H)           # a local offset (~0), not sx
        self.assertLess(abs(far), H)            # STILL local after the jump
        self.assertLess(abs(near - far), ts)    # barely moved despite the jump

    def test_facing_eases_toward_the_movement_heading(self):
        """P34.14: walking a direction turns the continuous facing angle toward
        that heading (east ~90°, north ~180°) — the cast faces where it moves."""
        c = _new_char()
        _ensure_anim(c)
        x, y = c.position
        for _ in range(10):                      # walk east
            x += 1
            c.position = (x, y)
            update_anim(c, 1 / 30.0)
        self.assertAlmostEqual(c.metadata["_anim"]["face_cur"], 90.0, delta=12)
        for _ in range(12):                      # then turn north
            y -= 1
            c.position = (x, y)
            update_anim(c, 1 / 30.0)
        self.assertAlmostEqual(c.metadata["_anim"]["face_cur"], 180.0, delta=12)

    def test_draw_at_every_facing_does_not_crash(self):
        import math
        from ui.body_renderer import draw_body
        c = _new_char()
        surf = pygame.Surface((96, 160))
        for deg in range(0, 360, 30):
            c.metadata.setdefault("_anim", _ensure_anim(c))["face_cur"] = deg
            c.metadata["_anim"]["face_target"] = deg
            draw_body(surf, c, 20, 40, 48, is_player=False)

    def test_ssaa_crisp_draw_renders_the_body(self):
        """P34.7: the oversampled crisp draw produces the character (non-empty)
        and doesn't crash."""
        from ui.body_renderer import draw_body_crisp
        c = _new_char()
        c.metadata.setdefault("_anim", _ensure_anim(c))["face_cur"] = 45
        surf = pygame.Surface((160, 220))
        surf.fill((0, 0, 0))
        draw_body_crisp(surf, c, 60, 90, 48, is_player=True)
        # something was drawn somewhere on the surface
        arr = pygame.surfarray.array3d(surf)
        self.assertGreater(int(arr.sum()), 0)

    def test_draw_projectile_kinds(self):
        surf = pygame.Surface((64, 64))
        for kind in ("arrow", "bolt", "stone", "spell", "unknown"):
            draw_projectile(surf, kind, 0, 0, 32)

    def test_class_weapon_table_complete(self):
        # Every class in the torso tint should appear in weapon table
        # (with possibly None for unarmed)
        for klass in CLASS_TORSO_TINT:
            self.assertIn(klass, CLASS_WEAPON)


class TestFormShading(unittest.TestCase):
    """ANIM_REALISM R1 — 2D body parts read as ROUNDED forms (a directional key
    light gives each limb a dark side, a lit core, and a highlight edge)."""

    def _shades_across(self, surf, x, y0, y1):
        arr = pygame.surfarray.array3d(surf)
        return {tuple(c) for c in arr[x, y0:y1].tolist() if tuple(c) != (0, 0, 0)}

    def test_a_limb_is_a_shaded_cylinder(self):
        from ui import body_parts as bp
        surf = pygame.Surface((80, 40))
        surf.fill((0, 0, 0))
        bp._limb(surf, (10, 20), (70, 20), (120, 90, 60), 14)
        shades = self._shades_across(surf, 40, 10, 30)
        self.assertGreaterEqual(len(shades), 3,
                                "a dark side, a lit core, and a highlight")

    def test_a_blade_is_two_tone_metal(self):
        from ui import body_parts as bp
        pose = {"r_hand": (20, 40), "r_elbow": (20, 60)}   # blade points up
        surf = pygame.Surface((60, 60))
        surf.fill((0, 0, 0))
        bp.draw_weapon(surf, "sword", pose, 30, 5)
        arr = pygame.surfarray.array3d(surf)
        lum = arr.reshape(-1, 3).max(axis=1)
        lit = lum[lum > 0]
        self.assertGreater(int(lit.max()), 190, "a lit blade edge")
        self.assertLess(int(lit.min()), 150, "a shadowed spine / grip")

    def test_robed_classes_wear_a_robe(self):
        from ui import body_parts as bp
        self.assertIn("wizard", bp.ROBE_CLASSES)
        self.assertIn("cleric", bp.ROBE_CLASSES)
        self.assertNotIn("warrior", bp.ROBE_CLASSES)

    def test_a_robe_is_a_filled_flared_skirt(self):
        from ui import body_parts as bp
        pose = {"l_hip": (44, 60), "r_hip": (56, 60),
                "l_foot": (46, 110), "r_foot": (54, 110)}
        surf = pygame.Surface((120, 130))
        surf.fill((0, 0, 0))
        bp.draw_robe(surf, pose, (90, 60, 140), 6)
        arr = pygame.surfarray.array3d(surf)
        painted = (arr.reshape(-1, 3).max(axis=1) > 0)
        # the hem is wider than the hips → the skirt flares (fills a broad band low)
        low = pygame.surfarray.array3d(surf)[:, 108]
        hem_px = int((low.max(axis=1) > 0).sum())
        self.assertGreater(hem_px, 12, "the hem flares wider than the hips")
        self.assertGreater(int(painted.sum()), 200, "a filled skirt")

    def test_staff_orb_glows(self):
        from ui import body_parts as bp
        pose = {"r_hand": (30, 30), "r_elbow": (30, 55)}
        surf = pygame.Surface((60, 60))
        surf.fill((0, 0, 0))
        bp.draw_weapon(surf, "staff", pose, 24, 4)
        arr = pygame.surfarray.array3d(surf)
        self.assertGreater(int(arr[..., 2].max()), 230, "a bright glowing core")

    def test_the_head_is_a_shaded_sphere(self):
        # a drawn head has a highlight lighter than its skin and a shaded side
        c = _new_char()
        c.metadata.setdefault("_anim", _ensure_anim(c))["face_cur"] = 0
        surf = pygame.Surface((120, 200))
        surf.fill((0, 0, 0))
        draw_body(surf, c, 40, 60, 48, is_player=True)
        arr = pygame.surfarray.array3d(surf)
        bright = int(arr.reshape(-1, 3).max(axis=1).max())
        self.assertGreater(bright, 180, "a lit highlight is present")


class TestGroundShadow(unittest.TestCase):
    """ANIM_REALISM R6 — a soft contact shadow grounds a figure and SHRINKS as it
    lifts off the ground (airborne reads)."""

    def _footprint(self, pose, fx, fy, H):
        from ui.body_renderer import _draw_ground_shadow
        surf = pygame.Surface((360, 360), pygame.SRCALPHA)
        _draw_ground_shadow(surf, pose, fx, fy, H)
        # the shadow is deliberately soft (low alpha) — count with a low threshold
        return pygame.mask.from_surface(surf, 5).count()

    def test_a_grounded_figure_casts_a_shadow(self):
        fx, fy, H = 180, 240, 100
        pose = {"l_foot": (fx - 10, fy), "r_foot": (fx + 10, fy)}
        self.assertGreater(self._footprint(pose, fx, fy, H), 0)

    def test_airborne_shadow_shrinks(self):
        fx, fy, H = 180, 240, 100
        grounded = {"l_foot": (fx - 10, fy), "r_foot": (fx + 10, fy)}
        airborne = {"l_foot": (fx - 6, fy - 80), "r_foot": (fx + 6, fy - 80)}
        g = self._footprint(grounded, fx, fy, H)
        a = self._footprint(airborne, fx, fy, H)
        self.assertLess(a, g, "an airborne figure's contact shadow shrinks")


if __name__ == "__main__":
    unittest.main()
