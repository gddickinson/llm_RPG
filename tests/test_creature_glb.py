"""#9 — the Quaternius GLB creature-model pipeline.

A GLB loads to per-primitive meshes with node WORLD transforms applied (so a
standing quadruped has a body-length-dominant bounding box, not a tiny cube),
bakes to a cached iso sprite, and resolves from a Character's model hint / name.
Unmodelled species fall back to None so the procedural creature still draws.
"""

import unittest

import numpy as np

from ui import creature_glb as cg
from ui import creature_pose, creature_render


class _Ch:
    """A minimal creature stand-in (name / id / metadata)."""
    def __init__(self, name="", cid="", model="", species=""):
        self.name = name
        self.id = cid
        self.hp = 10
        self.max_hp = 10
        from characters.character_types import CharacterClass
        self.character_class = CharacterClass.ANIMAL
        self.metadata = {"model": model, "species": species,
                         "_anim": {"facing": (0, 1), "moving": False,
                                   "idle_phase": 0.0, "clock": 0.0}}


class TestSpeciesResolution(unittest.TestCase):
    def test_name_keyword_matches(self):
        self.assertEqual(cg.species_of(_Ch(name="Grey Wolf")), "wolf")
        self.assertEqual(cg.species_of(_Ch(name="Red Fox")), "fox")

    def test_model_hint_wins(self):
        # "Aurochs" contains no model keyword — the explicit hint resolves it
        self.assertEqual(cg.species_of(_Ch(name="Aurochs", model="cow")), "cow")
        # and the hint beats a misleading name
        self.assertEqual(cg.species_of(_Ch(name="Mire Shark", model="shark")),
                         "shark")

    def test_boar_maps_to_pig(self):
        # the "boar" key resolves to the shared pig GLB
        self.assertEqual(cg.species_of(_Ch(name="Wild Boar")), "boar")
        self.assertEqual(cg.SPECIES_GLB["boar"], "pig")

    def test_unmodelled_is_none(self):
        self.assertIsNone(cg.species_of(_Ch(name="Goblin Shaman")))
        self.assertIsNone(cg.species_of(_Ch(name="Slime")))


class TestLoader(unittest.TestCase):
    """Node transforms must be applied — else the raw bind pose is a tiny cube."""

    @unittest.skipUnless(cg.GLB_OK, "pygltflib/numpy not available")
    def test_body_is_length_dominant(self):
        import os
        for sp, base in (("deer", "deer"), ("horse", "horse"), ("fox", "fox")):
            path = os.path.join(cg._DIR, base + ".glb")
            if not os.path.exists(path):
                continue
            meshes = cg.load_meshes(path)
            allv = np.concatenate([v for v, _, _ in meshes])
            dims = allv.max(0) - allv.min(0)
            # the raw (un-transformed) bind pose is a tiny ~0.05-unit cube; once
            # the node WORLD transforms (−90°X, ×100) are applied the model is
            # metres-scale and body-length/height dominates its narrow width
            self.assertGreater(max(dims), 1.0,
                               f"{sp}: node transforms not applied ({dims})")
            self.assertGreater(max(dims), 1.8 * min(dims),
                               f"{sp}: not a standing quadruped shape ({dims})")


class TestSprite(unittest.TestCase):
    @unittest.skipUnless(cg.GLB_OK, "pygltflib/numpy not available")
    def test_known_species_bakes_a_sprite(self):
        spr = cg.sprite("fox", 48)
        self.assertIsNotNone(spr)
        self.assertEqual(spr.get_size(), (48, 48))

    def test_unmodelled_species_is_none(self):
        self.assertIsNone(cg.sprite("griffon", 48))
        self.assertIsNone(cg.sprite("", 48))

    @unittest.skipUnless(cg.GLB_OK, "pygltflib/numpy not available")
    def test_sprite_for_char_flips_facing_east(self):
        left = cg.sprite_for_char(_Ch(name="Wolf"), 48, face_east=False)
        right = cg.sprite_for_char(_Ch(name="Wolf"), 48, face_east=True)
        self.assertIsNotNone(left)
        self.assertIsNotNone(right)
        self.assertEqual(left.get_size(), right.get_size())


class TestDispatch(unittest.TestCase):
    def test_modeled_creature_is_non_humanoid(self):
        # a creature with a model hint dispatches to creature_render
        self.assertEqual(creature_pose.body_plan(_Ch(name="Aurochs",
                                                      model="cow")),
                         "quadruped")

    def test_draw_creature_runs(self):
        import pygame
        pygame.init()
        surf = pygame.Surface((80, 80), pygame.SRCALPHA)
        # a modeled creature and an unmodelled one both draw without error
        for ch in (_Ch(name="Red Stag", model="deer"), _Ch(name="Slime")):
            plan = creature_pose.body_plan(ch)
            creature_render.draw_creature(surf, ch, 10, 10, 48, plan)


class TestIsoParity(unittest.TestCase):
    """The baked models bake at the iso camera, so the iso path uses them too."""

    @unittest.skipUnless(cg.GLB_OK, "pygltflib/numpy not available")
    def test_beast_sprite_for_modeled_creature(self):
        from ui import iso_actors
        self.assertIsNotNone(iso_actors.beast_sprite(_Ch(name="Wolf"), 48))

    def test_no_beast_sprite_for_humanoid(self):
        from ui import iso_actors
        from characters.character_types import CharacterClass
        ch = _Ch(name="Wolfgang")
        ch.character_class = CharacterClass.WARRIOR       # a person, not a beast
        self.assertIsNone(iso_actors.beast_sprite(ch, 48))

    def test_draw_actor_runs(self):
        import pygame
        pygame.init()
        from ui import iso_actors
        surf = pygame.Surface((120, 120), pygame.SRCALPHA)
        for ch in (_Ch(name="Aurochs", model="cow"), _Ch(name="Grey Wolf")):
            iso_actors.draw_actor(surf, ch, 60, 60, 48)


class TestMountModels(unittest.TestCase):
    """#9 — the trailing mount uses the baked GLB where one exists."""

    def test_mount_kinds_resolve(self):
        # horse/war_horse → horse, mule/donkey → donkey; carpet has no model
        self.assertEqual(cg.SPECIES_GLB.get("horse"), "horse")
        self.assertEqual(cg.SPECIES_GLB.get("war_horse"), "horse")
        self.assertEqual(cg.SPECIES_GLB.get("mule"), "donkey")
        self.assertNotIn("magic_carpet", cg.SPECIES_GLB)

    def test_draw_mount_runs_for_all_kinds(self):
        import pygame
        pygame.init()
        from ui.renderer_overlays import draw_mount
        surf = pygame.Surface((80, 80), pygame.SRCALPHA)
        for kind in ("horse", "war_horse", "mule", "donkey", "elephant",
                     "magic_carpet"):
            draw_mount(surf, kind, 10, 10, 48)      # modeled + fallback both draw


class TestRosterModels(unittest.TestCase):
    """Every new roster creature with a model hint has a real GLB behind it."""

    def test_wildlife_models_exist(self):
        from world.wildlife import ROSTER
        for sid, spec in ROSTER.items():
            model = spec.get("model")
            if model:
                self.assertTrue(cg.has_model(model),
                                f"wildlife {sid} model '{model}' missing")

    def test_monster_models_exist(self):
        from world.monsters import MONSTER_TEMPLATES
        for tid, spec in MONSTER_TEMPLATES.items():
            model = spec.get("model")
            if model:
                self.assertTrue(cg.has_model(model),
                                f"monster {tid} model '{model}' missing")


if __name__ == "__main__":
    unittest.main()
