"""T2.5 — realised ambitions change the world (shop/title effects)."""

import unittest

from engine import ambition_effects as ae


class _NPC:
    def __init__(self, meta):
        self.metadata = meta


class TestAmbitionEffects(unittest.TestCase):
    def test_master_flags(self):
        self.assertTrue(ae.is_master(_NPC({"master": True})))
        self.assertFalse(ae.is_master(_NPC({})))
        self.assertEqual(ae.title_prefix(_NPC({"master": True})), "Master ")
        self.assertEqual(ae.title_prefix(_NPC({})), "")

    def test_masterwork_stock(self):
        self.assertEqual(
            ae.masterwork_item(_NPC({"master": True}), "blacksmith"),
            "fortified_plate")
        self.assertIsNone(ae.masterwork_item(_NPC({}), "blacksmith"),
                          "a non-master has no masterwork")
        self.assertIsNone(ae.masterwork_item(_NPC({"master": True}), "tavern"),
                          "a tavernkeeper has no masterwork trade")

    def test_prospered_gold(self):
        self.assertEqual(ae.shop_gold_bonus(_NPC({"prospered": True})), 300)
        self.assertEqual(ae.shop_gold_bonus(_NPC({})), 0)


if __name__ == "__main__":
    unittest.main()
