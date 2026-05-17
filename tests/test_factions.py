"""Tests for the faction reputation system."""

import unittest

from characters.factions import (
    Faction, faction_of_class, is_hostile_pair,
    get_rep, set_rep, modify_rep, on_defeat, rep_label,
)


class FakePlayer:
    def __init__(self):
        self.metadata = {"faction_rep": {}}


class TestFactions(unittest.TestCase):
    def test_class_to_faction(self):
        self.assertEqual(faction_of_class("guard"), Faction.GUARDS)
        self.assertEqual(faction_of_class("brigand"), Faction.BRIGANDS)
        self.assertEqual(faction_of_class("monster"), Faction.MONSTERS)
        self.assertEqual(faction_of_class("nonsense"), Faction.NEUTRAL)

    def test_hostile_pairs(self):
        self.assertTrue(is_hostile_pair(Faction.BRIGANDS, Faction.GUARDS))
        self.assertTrue(is_hostile_pair(Faction.MONSTERS, Faction.VILLAGERS))
        self.assertFalse(is_hostile_pair(Faction.VILLAGERS, Faction.GUARDS))

    def test_rep_modification(self):
        p = FakePlayer()
        self.assertEqual(get_rep(p, Faction.GUARDS), 0)
        set_rep(p, Faction.GUARDS, 30)
        self.assertEqual(get_rep(p, Faction.GUARDS), 30)
        modify_rep(p, Faction.GUARDS, 15)
        self.assertEqual(get_rep(p, Faction.GUARDS), 45)
        modify_rep(p, Faction.GUARDS, -200)
        self.assertEqual(get_rep(p, Faction.GUARDS), -100)
        modify_rep(p, Faction.GUARDS, 500)
        self.assertEqual(get_rep(p, Faction.GUARDS), 100)

    def test_on_defeat_brigand(self):
        p = FakePlayer()
        deltas = on_defeat(p, "brigand")
        self.assertIn("guards", deltas)
        self.assertGreater(get_rep(p, Faction.GUARDS), 0)
        self.assertLess(get_rep(p, Faction.BRIGANDS), 0)

    def test_on_defeat_villager(self):
        p = FakePlayer()
        on_defeat(p, "villager")
        self.assertLess(get_rep(p, Faction.VILLAGERS), 0)
        self.assertLess(get_rep(p, Faction.GUARDS), 0)
        self.assertGreater(get_rep(p, Faction.BRIGANDS), 0)

    def test_rep_labels(self):
        self.assertEqual(rep_label(100), "revered")
        self.assertEqual(rep_label(60), "honored")
        self.assertEqual(rep_label(25), "friendly")
        self.assertEqual(rep_label(0), "neutral")
        self.assertEqual(rep_label(-30), "wary")
        self.assertEqual(rep_label(-70), "hostile")
        self.assertEqual(rep_label(-100), "hated")


if __name__ == "__main__":
    unittest.main()
