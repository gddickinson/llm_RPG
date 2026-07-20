"""Audit follow-up: the previously-stranded content is now reachable in-game.

George asked for a codebase review of unimplemented/unsurfaced code. The audit
found a set of items with NO acquisition path (no shop/loot/recipe/hoard) and a
monster that never spawned. This pins their surfacing so they can't silently
strand again.
"""

import json
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(__file__))


def _catalog_ids():
    ids = set()
    for cat in json.load(open(os.path.join(_ROOT, "data",
                                           "shop_catalogs.json"))).values():
        ids.update(cat)
    return ids


def _hoard_ids():
    ids = set()
    for lair in json.load(open(os.path.join(_ROOT, "data",
                                            "lairs.json"))).values():
        if isinstance(lair, dict):
            ids.update(lair.get("hoard", []))
    return ids


class TestStrandedItemsNowReachable(unittest.TestCase):
    SHOP_ITEMS = ["plate", "crossbow", "sling", "thrown_knife",
                  "explorers_chart", "holy_mace", "ring_strength",
                  "silent_boots"]
    HOARD_ITEMS = ["flaming_sword", "frost_dagger",
                   "manual_athletics", "manual_dexterity"]

    def test_shop_items_are_stocked(self):
        catalog = _catalog_ids()
        for iid in self.SHOP_ITEMS:
            self.assertIn(iid, catalog,
                          f"{iid} should be buyable from a merchant now")

    def test_hoard_items_are_dropped(self):
        hoard = _hoard_ids()
        for iid in self.HOARD_ITEMS:
            self.assertIn(iid, hoard,
                          f"{iid} should be in a lair hoard now")

    def test_crossbow_and_sling_match_their_sold_ammo(self):
        # the odd one: their ammo was sold but the weapons weren't
        catalog = _catalog_ids()
        self.assertTrue({"crossbow", "bolt"} <= catalog)
        self.assertTrue({"sling", "stone"} <= catalog)


class TestHillGiantSpawns(unittest.TestCase):
    def test_hill_giant_is_in_the_encounter_table(self):
        from world.monsters import encounter_table
        table = dict(encounter_table())
        self.assertIn("hill_giant", table)
        self.assertGreater(table["hill_giant"], 0)


if __name__ == "__main__":
    unittest.main()
