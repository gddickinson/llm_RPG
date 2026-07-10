"""Quest points + Adventurers' Guild tests (P4.3)."""

import unittest

from engine.game_engine import GameEngine
from quests.quest import QuestStatus


def _turn_in(engine, quest_id):
    quest = engine.quest_manager.get(quest_id)
    quest.status = QuestStatus.ACTIVE
    for obj in quest.objectives:
        obj.increment(obj.required)
    quest.update_status()
    return engine.turn_in_quest(quest_id)


class TestGuild(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.guild = self.engine.guild

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_turn_in_awards_quest_points(self):
        self.assertEqual(self.guild.quest_points(), 0)
        self.assertTrue(_turn_in(self.engine, "tavern_intro"))
        self.assertEqual(self.guild.quest_points(), 1)
        self.assertTrue(_turn_in(self.engine, "troll_hunt"))
        self.assertEqual(self.guild.quest_points(), 4)

    def test_radiant_quests_grant_no_points(self):
        self.engine.radiant_quests.run_morning()
        radiant = next(q for q in
                       self.engine.quest_manager.quests.values()
                       if q.id.startswith("radiant_"))
        _turn_in(self.engine, radiant.id)
        self.assertEqual(self.guild.quest_points(), 0)

    def test_rank_thresholds_and_announcement(self):
        self.assertIsNone(self.guild.rank())
        notes = self.guild.award_points(5)
        self.assertEqual(self.guild.rank(), "Member")
        self.assertTrue(any("names you Member" in n for n in notes))
        self.guild.award_points(5)
        self.assertEqual(self.guild.rank(), "Veteran")
        self.guild.award_points(5)
        self.assertEqual(self.guild.rank(), "Champion")

    def test_member_perk_more_radiant_notices(self):
        self.assertEqual(self.guild.radiant_cap_bonus(), 0)
        self.guild.award_points(5)
        self.assertEqual(self.guild.radiant_cap_bonus(), 2)

    def test_veteran_perk_faster_teleports(self):
        self.guild.award_points(10)
        self.player.position = (1, 1)
        self.engine.travel_system.teleport(0)
        from engine.travel import TELEPORT_COOLDOWN_MIN
        remaining = self.engine.travel_system.cooldown_remaining()
        self.assertLessEqual(remaining, TELEPORT_COOLDOWN_MIN // 2)

    def test_champion_perk_fourth_companion(self):
        cm = self.engine.companion_manager
        recruitables = [n for n in
                        self.engine.npc_manager.npcs.values()
                        if getattr(n.character_class, "value", "") in
                        ("warrior", "bard", "cleric", "wizard", "ranger",
                         "paladin") and n.is_active()]
        if len(recruitables) < 1:
            self.skipTest("no recruitable NPCs")
        # Fake a full party of 3
        cm.party = ["a", "b", "c"]
        npc = recruitables[0]
        npc.modify_relationship(self.player.id, 50)
        self.assertIn("full", cm.can_recruit(npc))
        self.guild.award_points(15)
        self.assertEqual(cm.can_recruit(npc), "",
                         "Champion should allow a 4th companion")

    def test_status_line(self):
        self.guild.award_points(6)
        line = self.guild.status_line()
        self.assertIn("6", line)
        self.assertIn("Member", line)

    def test_points_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.guild.award_points(7)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="g")
            self.player.metadata["quest_points"] = 0
            self.assertTrue(sm.load(self.engine, name="g"))
            self.assertEqual(self.engine.guild.quest_points(), 7)
            self.assertEqual(self.engine.guild.rank(), "Member")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
