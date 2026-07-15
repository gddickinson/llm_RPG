"""Supply-chain origins (P16.1): every item has a producer."""

import os as _os
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from engine import production as pr                      # noqa: E402


class TestOrigins(unittest.TestCase):
    def test_gathered_raw(self):
        o = pr.origin_of("iron_ore")
        self.assertEqual(o["kind"], pr.RAW)
        self.assertEqual(o["profession"], "miner")
        self.assertEqual(o["source"], "mountain")
        self.assertEqual(o["tool"], "pickaxe")

    def test_crafted_good(self):
        o = pr.origin_of("sword")
        self.assertEqual(o["kind"], pr.CRAFTED)
        self.assertEqual(o["profession"], "smith")
        self.assertEqual(o["workstation"], "forge")
        self.assertIn("iron_bar", o["inputs"])

    def test_authored_raws(self):
        self.assertEqual(pr.origin_of("herb_bundle")["profession"], "forager")
        self.assertEqual(pr.origin_of("wheat_sheaf")["profession"], "farmer")
        self.assertEqual(pr.origin_of("wolf_pelt")["source"], "beast")

    def test_unknown_item_has_no_origin(self):
        self.assertIsNone(pr.origin_of("gold"))
        self.assertFalse(pr.is_raw("gold"))
        self.assertFalse(pr.is_crafted("gold"))

    def test_raw_and_crafted_are_disjoint_and_populated(self):
        raws = set(pr.raw_materials())
        crafted = set(pr.crafted_goods())
        self.assertTrue(raws and crafted)
        self.assertEqual(raws & crafted, set())


class TestProfessions(unittest.TestCase):
    def test_every_profession_maps_to_a_real_skill(self):
        from engine.skill_progression import SKILLS
        for prof in pr.all_professions():
            self.assertIn(pr.skill_for_profession(prof), SKILLS)

    def test_producers(self):
        self.assertIn("iron_ore", pr.producers("miner"))
        self.assertIn("sword", pr.producers("smith"))
        # a producer only makes what carries its profession
        for item in pr.producers("miner"):
            self.assertEqual(pr.profession_of(item), "miner")

    def test_source_only_for_raws(self):
        self.assertIsNotNone(pr.source_of("iron_ore"))
        self.assertIsNone(pr.source_of("sword"))

    def test_inputs_only_for_crafted(self):
        self.assertEqual(pr.inputs_of("iron_ore"), {})
        self.assertTrue(pr.inputs_of("sword"))


class TestCoverageAndChain(unittest.TestCase):
    def test_every_gathering_tier_and_recipe_has_an_origin(self):
        from items.data_loader import load_data_file
        idx = pr.all_origins()
        for node in load_data_file("gathering.json").values():
            for tier in node.get("tiers", []):
                self.assertIn(tier["item"], idx)
        for out in load_data_file("recipes.json"):
            self.assertIn(out, idx)

    def test_crafted_goods_ground_out_in_raw_materials(self):
        # walking a crafted good's inputs must eventually reach raws —
        # no crafted item is made from thin air.
        def grounds(item, seen):
            o = pr.origin_of(item)
            if o is None:
                return False              # a base/bought item, not produced
            if o["kind"] == pr.RAW:
                return True
            if item in seen:
                return False
            seen = seen | {item}
            return any(grounds(i, seen) or pr.origin_of(i) is None
                       for i in o.get("inputs", {}))
        for good in pr.crafted_goods():
            self.assertTrue(grounds(good, set()),
                            f"{good} never reaches a raw material")

    def test_all_inputs_are_known_items(self):
        from items.item_registry import ITEM_REGISTRY
        for good in pr.crafted_goods():
            for inp in pr.inputs_of(good):
                self.assertIn(inp, ITEM_REGISTRY,
                              f"{good} needs unknown input {inp}")


if __name__ == "__main__":
    unittest.main()
