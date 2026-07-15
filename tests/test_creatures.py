"""P34.18 — creature body plans: classification + quadruped projection + draw."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_crit_"))

import unittest
import pygame
pygame.init()

from ui import creature_pose as cp


class _Cls:
    def __init__(self, v):
        self.value = v


class _Char:
    def __init__(self, name, klass="monster", meta=None):
        self.name = name
        self.id = "enc_" + name.lower().replace(" ", "_") + "_x"
        self.character_class = _Cls(klass)
        self.metadata = meta or {}
        self.position = (0, 10)
        self.hp = 8
        self.max_hp = 12

    def is_alive(self):
        return True


class TestClassification(unittest.TestCase):
    def test_beasts_by_species(self):
        self.assertEqual(cp.body_plan(_Char("Wolf")), "quadruped")
        self.assertEqual(cp.body_plan(_Char("Red Fox")), "quadruped")
        self.assertEqual(cp.body_plan(_Char("Wild Boar")), "quadruped")
        self.assertEqual(cp.body_plan(_Char("Green Slime")), "slime")
        self.assertEqual(cp.body_plan(_Char("Marsh Wisp")), "wisp")
        self.assertEqual(cp.body_plan(_Char("Raven")), "avian")
        self.assertEqual(cp.body_plan(_Char("Giant Bat")), "avian")
        self.assertEqual(cp.body_plan(_Char("Cave Spider")), "arachnid")
        self.assertEqual(cp.body_plan(_Char("Scorpion")), "arachnid")

    def test_wildlife_is_animal_class(self):
        self.assertEqual(cp.body_plan(_Char("Deer", klass="animal")), "quadruped")
        self.assertEqual(cp.body_plan(_Char("Rabbit", klass="animal")), "quadruped")

    def test_humanoid_monsters_stay_puppets(self):
        for n in ("Goblin", "Troll", "Orc", "Skeleton", "Bandit"):
            self.assertEqual(cp.body_plan(_Char(n)), "humanoid")

    def test_npcs_never_reclassified(self):
        # a villager named 'Will' must NOT become a wisp (class gate)
        self.assertEqual(cp.body_plan(_Char("Will", klass="villager")), "humanoid")
        self.assertEqual(cp.body_plan(_Char("Catherine", klass="merchant")),
                         "humanoid")

    def test_explicit_metadata_hint_wins(self):
        c = _Char("Thing", klass="villager", meta={"body_plan": "slime"})
        self.assertEqual(cp.body_plan(c), "slime")


class TestQuadrupedPose(unittest.TestCase):
    def test_has_four_legs_and_a_head(self):
        p = cp.quadruped_points(60, 120, 60, 1.0, 90, moving=True)
        self.assertEqual(set(p["legs"].keys()), {"fl", "fr", "bl", "br"})
        for k in ("head", "snout", "tail_tip", "shoulder", "hip"):
            self.assertIn(k, p)

    def test_side_walk_strides_the_legs(self):
        # over the cycle a leg's foot sweeps fore-aft (at profile that's x)
        xs = [cp.quadruped_points(60, 120, 60, ph, 90)["legs"]["fl"][1][0]
              for ph in (0.0, 0.5, 1.0, 1.5)]
        self.assertGreater(max(xs) - min(xs), 2.0)


class TestCombatMotion(unittest.TestCase):
    def test_attack_lunges_and_hurt_recoils_opposite_ways(self):
        rest = cp.quadruped_points(60, 120, 60, 0.0, 90)
        lunge = cp.quadruped_points(60, 120, 60, 0.0, 90, attack=0.5)
        hurt = cp.quadruped_points(60, 120, 60, 0.0, 90, hurt=0.5)
        self.assertNotEqual(rest["head"][0], lunge["head"][0])   # pounce shifts it
        self.assertNotEqual(rest["head"][0], hurt["head"][0])    # recoil too
        # forward on the strike, backward when hit
        self.assertNotEqual(lunge["head"][0] > rest["head"][0],
                            hurt["head"][0] > rest["head"][0])


class TestDraw(unittest.TestCase):
    def test_draw_each_plan_without_crashing(self):
        from ui import body_renderer
        surf = pygame.Surface((96, 128))
        for name, klass in (("Wolf", "monster"), ("Slime", "monster"),
                            ("Wisp", "monster"), ("Deer", "animal"),
                            ("Raven", "monster"), ("Cave Spider", "monster")):
            c = _Char(name, klass)
            body_renderer.draw_body(surf, c, 20, 40, 48, is_player=False)


if __name__ == "__main__":
    unittest.main()
