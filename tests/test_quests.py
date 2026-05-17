"""Tests for the quest system."""

import unittest

from quests import (
    Quest, QuestObjective, QuestStatus, ObjectiveType,
    QuestManager, create_quest,
)


class TestQuestObjective(unittest.TestCase):
    def test_completion(self):
        obj = QuestObjective(obj_type=ObjectiveType.KILL,
                             target="npc1", required=3)
        self.assertFalse(obj.is_complete())
        obj.increment()
        obj.increment()
        self.assertFalse(obj.is_complete())
        newly = obj.increment()
        self.assertTrue(obj.is_complete())
        self.assertTrue(newly)
        # Won't double-count
        newly = obj.increment()
        self.assertFalse(newly)


class TestQuestManager(unittest.TestCase):
    def setUp(self):
        self.qm = QuestManager()

    def test_offer_and_accept(self):
        q = self.qm.offer_quest("troll_hunt")
        self.assertIsNotNone(q)
        self.assertEqual(q.status, QuestStatus.AVAILABLE)
        self.assertTrue(self.qm.accept_quest("troll_hunt"))
        self.assertEqual(q.status, QuestStatus.ACTIVE)

    def test_kill_objective_progress(self):
        self.qm.offer_quest("troll_hunt")
        self.qm.accept_quest("troll_hunt")
        self.qm.on_npc_defeated("troll_brigand_01", "brigand")
        q = self.qm.get("troll_hunt")
        self.assertEqual(q.status, QuestStatus.COMPLETED)

    def test_fetch_objective(self):
        self.qm.offer_quest("herb_gathering")
        self.qm.accept_quest("herb_gathering")
        self.qm.on_item_acquired("herb_bundle", quantity=2)
        q = self.qm.get("herb_gathering")
        self.assertEqual(q.status, QuestStatus.ACTIVE)
        self.qm.on_item_acquired("herb_bundle", quantity=1)
        self.assertEqual(q.status, QuestStatus.COMPLETED)

    def test_turn_in(self):
        # Fake player
        class P:
            def __init__(self):
                self.gold = 0
                self.inventory = []
                self.metadata = {"xp": 0}
        p = P()
        self.qm.offer_quest("troll_hunt")
        self.qm.accept_quest("troll_hunt")
        self.qm.on_npc_defeated("troll_brigand_01")
        ok = self.qm.turn_in("troll_hunt", p)
        self.assertTrue(ok)
        self.assertEqual(p.gold, 100)
        self.assertGreater(p.metadata["xp"], 0)
        self.assertTrue(any(getattr(i, "id", "") == "longsword"
                            for i in p.inventory))

    def test_save_load(self):
        self.qm.offer_quest("troll_hunt")
        self.qm.accept_quest("troll_hunt")
        self.qm.on_npc_defeated("troll_brigand_01")
        d = self.qm.to_dict()
        qm2 = QuestManager()
        qm2.from_dict(d)
        self.assertIn("troll_hunt", qm2.quests)
        self.assertEqual(qm2.quests["troll_hunt"].status,
                         QuestStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
