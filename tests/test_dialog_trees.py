"""Tests for branching dialog trees."""

import unittest

from engine.dialog_trees import tree_for, DialogTree


class FakeClass:
    def __init__(self, value):
        self.value = value


class FakeNPC:
    def __init__(self, npc_id, klass):
        self.id = npc_id
        self.character_class = FakeClass(klass)


class TestDialogTrees(unittest.TestCase):
    def test_tavernkeeper_specific(self):
        t = tree_for(FakeNPC("tavernkeeper_01", "merchant"))
        self.assertIsInstance(t, DialogTree)
        self.assertEqual(t.root, "root")
        self.assertGreater(len(t.nodes["root"].options), 1)

    def test_class_based(self):
        for klass in ("guard", "merchant", "bard", "cleric"):
            t = tree_for(FakeNPC("xyz", klass))
            self.assertIsNotNone(t, klass)

    def test_unknown_class(self):
        t = tree_for(FakeNPC("xyz", "nonsense"))
        self.assertIsNone(t)

    def test_guard_offers_troll_hunt(self):
        t = tree_for(FakeNPC("guard_01", "guard"))
        # One option should have offer_quest action
        actions = []
        for node in t.nodes.values():
            for opt in node.options:
                actions.append(opt.action)
        self.assertTrue(any("offer_quest:troll_hunt" in a for a in actions))


if __name__ == "__main__":
    unittest.main()
