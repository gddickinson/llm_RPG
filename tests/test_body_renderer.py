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


class TestFace(unittest.TestCase):
    """ANIM_REALISM G1 — the face reads as a face: eyes have a light sclera +
    catchlight (not a solid black void)."""

    def test_neutral_eye_has_a_light_sclera(self):
        from ui import body_parts as bp
        surf = pygame.Surface((160, 160))
        surf.fill((0, 0, 0))
        bp.draw_face(surf, 80, 80, 44, "neutral")
        arr = pygame.surfarray.array3d(surf)
        bright = int(arr.reshape(-1, 3).max(axis=1).max())
        self.assertGreater(bright, 200,
                           "the eye has a light sclera/catchlight, not a void")

    def test_attack_action_drives_a_fighting_face(self):
        from ui import char_face
        self.assertEqual(char_face.EMOTE_EXPR.get("attack"), "angry")


class TestActionAndAnatomy(unittest.TestCase):
    """G3 attack lunge (a strike drives the body forward) + G4 directional boots."""

    def test_attack_lunge_peaks_mid_strike(self):
        from ui import char_motion as cm
        self.assertLess(cm.attack_lunge(cm.ATTACK_DUR), 0.05)          # just begun
        self.assertGreater(cm.attack_lunge(cm.ATTACK_DUR * 0.5), 0.9)  # peak drive
        self.assertEqual(cm.attack_lunge(0.0), 0.0)                    # at rest

    def test_martial_classes_fly_a_cape(self):
        from ui import char_flow
        for cls in ("warrior", "knight", "fighter", "barbarian"):
            self.assertIn(cls, char_flow.CLOAK_CLASSES, f"{cls} wears a cape (H7)")

    def test_hairstyles_vary_across_a_crowd(self):
        from ui.body_renderer import _hair_style
        styles = {_hair_style(type("C", (), {"id": f"npc_{i}"})())
                  for i in range(48)}
        self.assertGreaterEqual(len(styles), 3, "H4 a crowd shows varied hair")
        self.assertTrue(styles <= {"short", "long", "bun", "bald"})

    def test_cast_glow_is_bright(self):
        from ui.body_renderer import _cast_glow
        surf = pygame.Surface((100, 100))
        surf.fill((0, 0, 0))
        _cast_glow(surf, 50, 50, 9)
        arr = pygame.surfarray.array3d(surf)
        self.assertGreater(int(arr.reshape(-1, 3).max(axis=1).max()), 150,
                           "H2 the cast channel glows")

    def test_boot_points_toward_the_facing(self):
        from ui import body_parts as bp

        def span(prof):
            surf = pygame.Surface((140, 70))
            surf.fill((0, 0, 0))
            pose = {"l_hip": (70, 12), "l_knee": (70, 30), "l_foot": (70, 52),
                    "r_hip": (70, 12), "r_knee": (70, 30), "r_foot": (70, 52),
                    "fdir": prof}
            bp.draw_legs(surf, pose, (80, 70, 60), (58, 44, 34), 7)
            xs = [x for x in range(140) for y in range(46, 60)
                  if surf.get_at((x, y))[:3] == (58, 44, 34)]
            return (min(xs), max(xs)) if xs else (70, 70)

        lmin, _ = span(-1)
        _, rmax = span(1)
        cmin, cmax = span(0)
        self.assertLess(lmin, cmin, "a left-facing boot's toe reaches further left")
        self.assertGreater(rmax, cmax, "a right-facing boot's toe reaches right")


class TestGear(unittest.TestCase):
    """G5 — class gear: armored shoulder plates, skulker hoods."""

    def test_class_gear_sets(self):
        from ui import body_parts as bp
        self.assertIn("warrior", bp.ARMOR_CLASSES)
        self.assertIn("rogue", bp.HOOD_CLASSES)
        self.assertNotIn("wizard", bp.ARMOR_CLASSES)   # robed, not plated

    def test_worn_metal_armor_drives_pauldrons(self):
        # H3: equipping plate shows shoulder plates on ANY class
        from ui import char_motion

        class _Item:
            id = "plate_armor"
            name = "Plate Armor"

        class _C:
            equipment = None
        c = _C()
        self.assertFalse(char_motion.has_metal_armor(c), "unarmored")
        c.equipment = {"armor": _Item()}
        self.assertTrue(char_motion.has_metal_armor(c), "worn plate reads metal")

    def test_pauldrons_and_hood_draw(self):
        from ui import body_parts as bp
        surf = pygame.Surface((100, 100))
        surf.fill((0, 0, 0))
        pose = {"l_sh": (38, 40), "r_sh": (62, 40),
                "head": (50, 30), "head_r": 8}
        bp.draw_pauldrons(surf, pose, (185, 188, 196), 7)
        bp.draw_hood(surf, pose, (40, 44, 40), 8)
        self.assertGreater(pygame.mask.from_surface(surf, 8).count(), 20)


class TestRelight(unittest.TestCase):
    """H6 — dynamic directional relight of the character sprite."""

    def test_relight_darkens_the_far_side_and_keeps_alpha(self):
        from ui.body_draw import apply_relight, NUMPY_OK
        if not NUMPY_OK:
            self.skipTest("numpy required")
        s = pygame.Surface((40, 40), pygame.SRCALPHA)
        s.fill((255, 255, 255, 255))
        apply_relight(s, (-1.0, 0.0, (255, 255, 255), (60, 60, 60)))  # light ←
        left = s.get_at((4, 20))[0]
        right = s.get_at((36, 20))[0]
        self.assertGreater(left, right, "the light-facing side is brighter")
        self.assertEqual(s.get_at((4, 20))[3], 255, "alpha preserved (no halo)")

    def test_relight_noop_without_light(self):
        from ui.body_draw import apply_relight
        s = pygame.Surface((20, 20), pygame.SRCALPHA)
        s.fill((200, 200, 200, 255))
        apply_relight(s, None)                       # no light → unchanged
        self.assertEqual(s.get_at((10, 10)), (200, 200, 200, 255))


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


class TestPartialAnimBackfill(unittest.TestCase):
    """A PARTIAL `_anim` dict is minted elsewhere before a body is ever
    rendered — a world-spell caster does `setdefault("_anim", {})["facing"]=…`
    (engine/spell_world). `_ensure_anim` must backfill the missing keys so the
    render loop never KeyErrors on `prev_pos` / `walk_phase`."""

    def test_ensure_anim_backfills_a_partial_dict(self):
        c = _new_char()
        c.metadata["_anim"] = {"facing": (1, 0)}       # only 'facing', as cast
        anim = _ensure_anim(c)
        self.assertIn("prev_pos", anim)
        self.assertIn("walk_phase", anim)
        self.assertEqual(anim["facing"], (1, 0), "the existing key is kept")

    def test_update_anim_survives_a_partial_dict(self):
        c = _new_char()
        c.metadata["_anim"] = {"facing": (0, 1)}       # partial, no prev_pos
        # Previously KeyError: 'prev_pos' — must not raise now.
        update_anim(c, 1.0 / 30.0)
        update_anim(c, 1.0 / 30.0)
        self.assertIn("prev_pos", c.metadata["_anim"])


if __name__ == "__main__":
    unittest.main()
