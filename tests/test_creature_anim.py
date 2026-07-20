"""#9b — ANIMATED creatures from the Quaternius GLB skeletal clips.

The rigged GLB clips (Walk/Idle/Attack/Death) are skinned + baked per phase, so
a beast strides/breathes/strikes instead of standing frozen. Cached, with a
graceful fallback to the static bind-pose sprite.
"""

import math
import unittest

from ui import creature_anim as ca


class _Ch:
    def __init__(self, name="Deer", anim=None, alive=True):
        self.name = name
        self.id = name.lower()
        self.metadata = {"_anim": anim if anim is not None else {}}
        self._alive = alive

    def is_alive(self):
        return self._alive


def _walking(phase):
    return _Ch("Deer", {"moving": True, "move_phase": phase, "facing": (1, 0)})


class TestActionPhase(unittest.TestCase):
    def test_moving_is_walk(self):
        act, ph = ca._action_and_phase(_walking(0.5))
        self.assertEqual(act, "walk")
        self.assertAlmostEqual(ph, 0.5, places=5)

    def test_still_is_idle(self):
        act, _ = ca._action_and_phase(_Ch("Deer", {"moving": False,
                                                    "idle_phase": 0.0}))
        self.assertEqual(act, "idle")

    def test_attacking(self):
        act, _ = ca._action_and_phase(_Ch("Deer", {"atk_t": 0.16}))
        self.assertEqual(act, "attack")

    def test_dead(self):
        act, ph = ca._action_and_phase(_Ch("Deer", {}, alive=False))
        self.assertEqual(act, "dead")
        self.assertEqual(ph, 1.0)


@unittest.skipUnless(ca._OK, "pygltflib/numpy not available")
class TestClips(unittest.TestCase):
    def test_walk_clip_present(self):
        self.assertEqual(ca.clip_for("deer", "walk"), "Walk")

    def test_attack_falls_back_to_species_variant(self):
        # the deer has no plain 'Attack' — it uses a headbutt/kick variant
        self.assertIn(ca.clip_for("deer", "attack"),
                      ("Attack", "Attack_Headbutt", "Attack_Kick"))

    def test_unmodelled_species(self):
        self.assertIsNone(ca.clip_for("griffon", "walk"))


@unittest.skipUnless(ca._OK, "pygltflib/numpy not available")
class TestBakedFrames(unittest.TestCase):
    def test_walking_returns_a_sprite(self):
        spr = ca.animated_sprite(_walking(0.0), 48)
        self.assertIsNotNone(spr)
        self.assertEqual(spr.get_size(), (48, 48))

    def test_walk_frames_differ(self):
        import pygame
        a = ca.animated_sprite(_walking(0.0), 48)
        b = ca.animated_sprite(_walking(0.5), 48)   # opposite side of the cycle
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(pygame.image.tostring(a, "RGBA"),
                            pygame.image.tostring(b, "RGBA"),
                            "the walk cycle must actually move the legs")

    def test_unmodelled_is_none(self):
        self.assertIsNone(ca.animated_sprite(_Ch("Goblin"), 48))

    def test_face_east_flips(self):
        import pygame
        left = ca.animated_sprite(_walking(0.25), 48, face_east=False)
        right = ca.animated_sprite(_walking(0.25), 48, face_east=True)
        self.assertNotEqual(pygame.image.tostring(left, "RGBA"),
                            pygame.image.tostring(right, "RGBA"))


class TestRenderIntegration(unittest.TestCase):
    def test_top_down_and_iso_draw_a_moving_beast(self):
        import pygame
        pygame.init()
        from world.wildlife import build_wildlife
        from ui import creature_render, creature_pose, iso_actors
        deer = build_wildlife("deer", (5, 5))
        deer.metadata.setdefault("_anim", {}).update(
            {"moving": True, "move_phase": 0.3, "facing": (1, 0)})
        surf = pygame.Surface((120, 120), pygame.SRCALPHA)
        creature_render.draw_creature(surf, deer, 10, 10, 48,
                                      creature_pose.body_plan(deer))
        iso_actors.draw_actor(surf, deer, 60, 60, 48)


if __name__ == "__main__":
    unittest.main()
