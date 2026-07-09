"""Radiant quest generation tests (P4.1)."""

import unittest

from engine.game_engine import GameEngine
from quests.quest import QuestStatus
from quests.radiant import MAX_ACTIVE, EXPIRY_DAYS, BOARD_LOCATION


class TestRadiantQuests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.gen = self.engine.radiant_quests
        self.qm = self.engine.quest_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _radiants(self):
        return [q for q in self.qm.quests.values()
                if q.id.startswith("radiant_")]

    def test_morning_generates_valid_posted_quests(self):
        notes = self.gen.run_morning()
        radiants = self._radiants()
        self.assertGreaterEqual(len(radiants), 1)
        board = self.engine.quest_board_manager.board_at(BOARD_LOCATION)
        for quest in radiants:
            self.assertEqual(quest.status, QuestStatus.AVAILABLE)
            self.assertIn(quest.id, board.posted_quest_ids)
            self.assertTrue(quest.giver_id)
            self.assertGreater(quest.reward_gold, 0)
        self.assertTrue(any("tavern board" in n for n in notes))

    def test_cap_respected_across_mornings(self):
        for day in range(6):
            self.engine.world.time = day * 24 * 60 + 60
            self.gen.run_morning()
        available = [q for q in self._radiants()
                     if q.status == QuestStatus.AVAILABLE]
        self.assertLessEqual(len(available), MAX_ACTIVE)

    def test_shortage_becomes_fetch_quest(self):
        self.engine.world_director._apply(
            {"type": "shortage", "item_id": "ale"})
        spec = self.gen._from_shortage()
        self.assertIsNotNone(spec)
        title, obj_type, target, count, _ = spec
        self.assertEqual((obj_type, target), ("fetch", "ale"))
        self.assertIn("Shortage", title)

    def test_sighted_monster_becomes_bounty(self):
        from world.monsters import build_monster
        wolf = build_monster("wolf", (50, 50))
        self.engine.npc_manager.add_npc(wolf)
        spec = self.gen._from_monsters()
        self.assertIsNotNone(spec)
        title, obj_type, target, count, _ = spec
        self.assertEqual(obj_type, "kill")
        self.assertIn("Bounty", title)

    def test_radiant_kill_quest_completable(self):
        from world.monsters import build_monster
        wolf = build_monster("wolf", (50, 50))
        self.engine.npc_manager.add_npc(wolf)
        # Force the bounty path for determinism
        self.gen._from_shortage = lambda: None
        quest = self.gen._generate(0, 0)
        self.assertEqual(quest.objectives[0].obj_type.value, "kill")
        self.qm.quests[quest.id] = quest
        self.qm.accept_quest(quest.id)
        self.qm.on_npc_defeated(wolf.id, wolf.character_class.value)
        self.assertEqual(self.qm.get(quest.id).status,
                         QuestStatus.COMPLETED)

    def test_stale_radiants_withdrawn(self):
        self.engine.world.time = 0
        self.gen.run_morning()
        before = [q.id for q in self._radiants()]
        self.assertTrue(before)
        self.engine.world.time = (EXPIRY_DAYS + 1) * 24 * 60
        self.gen.run_morning()
        board = self.engine.quest_board_manager.board_at(BOARD_LOCATION)
        for qid in before:
            self.assertNotIn(qid, self.qm.quests)
            self.assertNotIn(qid, board.posted_quest_ids)

    def test_accepted_radiants_never_withdrawn(self):
        self.engine.world.time = 0
        self.gen.run_morning()
        quest = self._radiants()[0]
        self.qm.accept_quest(quest.id)
        self.engine.world.time = (EXPIRY_DAYS + 2) * 24 * 60
        self.gen.run_morning()
        self.assertIn(quest.id, self.qm.quests)

    def test_rewards_scale_with_level(self):
        q1 = self.gen._generate(0, 0)
        self.engine.player.level = 10
        q2 = self.gen._generate(1, 0)
        self.assertGreater(q2.reward_gold, q1.reward_gold)
        self.assertGreater(q2.reward_xp, q1.reward_xp)

    def test_radiants_survive_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.gen.run_morning()
        ids = [q.id for q in self._radiants()]
        self.assertTrue(ids)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="r")
            self.qm.quests = {}
            self.assertTrue(sm.load(self.engine, name="r"))
            for qid in ids:
                self.assertIn(qid, self.engine.quest_manager.quests)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_day_change_generates_board_notices(self):
        now = self.engine.world.time
        self.engine.world.time = ((now // (24 * 60)) + 1) * 24 * 60
        self.engine.advance_turn()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-10:])
        self.assertIn("[Board]", log)


if __name__ == "__main__":
    unittest.main()
