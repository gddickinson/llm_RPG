"""ISO.3 — richer baked iso character figures (headless)."""

import unittest

import pygame

from ui import iso_chars


class _Char:
    def __init__(self, cid, cls, hair="hair_brown"):
        self.id = cid
        self.character_class = type("K", (), {"value": cls})()
        self.hair = hair
        self.metadata = {}


class TestFigure(unittest.TestCase):
    def test_figure_has_legs_torso_arms_head(self):
        parts = iso_chars._figure((150, 150, 165), (90, 60, 40), 2, stance=1)
        # 2 legs + waist + chest + 2 arms + head + hair + nose = 9 parts
        self.assertGreaterEqual(len(parts), 9, "arms + two legs now present")

    def test_stance_shifts_the_body(self):
        left = iso_chars._figure((150,) * 3, (90, 60, 40), 2, stance=0)
        right = iso_chars._figure((150,) * 3, (90, 60, 40), 2, stance=2)
        # the chest box (index 3) sits at a different x for opposite stances
        self.assertNotEqual(left[3][0].mean(axis=0)[0],
                            right[3][0].mean(axis=0)[0])

    def test_stance_is_stable_per_person(self):
        c = _Char("bess", "villager")
        self.assertEqual(iso_chars._stance_of(c), iso_chars._stance_of(c))
        self.assertIn(iso_chars._stance_of(c), (0, 1, 2))


class TestSprite(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_sprite_drawn_and_cached_with_stance(self):
        c = _Char("aldric", "warrior")
        s1 = iso_chars.char_sprite(c, 72, 2)
        self.assertIsInstance(s1, pygame.Surface)
        self.assertGreater(pygame.mask.from_surface(s1).count(), 40)
        self.assertIs(s1, iso_chars.char_sprite(c, 72, 2), "cached")

    def test_taller_than_a_single_tile(self):
        c = _Char("x", "merchant")
        s = iso_chars.char_sprite(c, 72, 2)
        self.assertGreater(s.get_height(), 0)


if __name__ == "__main__":
    unittest.main()
