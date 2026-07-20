"""NPC adventuring (George: the world's OTHER heroes go on adventures too). An
adventurer NPC adopts an unresolved, player-unstarted adventure, works it act
by act over days, and RESOLVES it — reshaping the world under a [Legend]."""

import os
import unittest

from engine.game_engine import GameEngine


class TestNpcAdventuring(unittest.TestCase):
    def setUp(self):
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.na = self.e.npc_adventuring

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def _strong_hero(self):
        for aid in self.e.adventurers.living():
            h = self.e.npc_manager.get_npc(aid)
            if h and h.level >= 5:
                return h
        return None

    def test_seasoned_adventurers_exist(self):
        self.assertIsNotNone(self._strong_hero(),
                             "the roster has heroes strong enough to adventure")

    def test_open_adventures_are_the_unstarted_ones(self):
        opens = self.na._open_adventures()
        self.assertIn("blackbanner", opens)
        # once the player begins one, it is no longer open to NPCs
        self.e.accept_quest("q_blackbanner_raids")
        self.assertNotIn("blackbanner", self.na._open_adventures())

    def test_an_npc_works_and_resolves_an_adventure(self):
        hero = self._strong_hero()
        self.na.active[hero.id] = {"adv": "wychwood", "act": 1, "day": 0}
        # advance act by act (ACT_DAYS apart) until it resolves
        day = 0
        for _ in range(12):
            day += 2
            self.na.run_day(day)
            if self.e.wychwood.is_resolved():
                break
        self.assertTrue(self.e.wychwood.is_resolved(),
                        "the NPC eventually ends the adventure")
        beats = [h["event"] for h in self.e.memory_manager.game_history]
        self.assertTrue(any("[Legend]" in b and hero.name in b for b in beats),
                        "the deed enters legend under the hero's name")

    def test_a_resolved_adventure_fails_the_players_dead_end_quests(self):
        hero = self._strong_hero()
        self.na.active[hero.id] = {"adv": "wychwood", "act": 3, "day": 0}
        self.na.run_day(2)     # act 3 -> finish
        from quests.quest import QuestStatus
        q = self.e.quest_manager.quests["q_wychwood_vanishings"]
        self.assertEqual(q.status, QuestStatus.FAILED,
                         "a now-impossible quest can't be accepted")
        self.assertEqual(self.e.quests_offered_by("granny_esk"), [],
                         "the giver no longer offers it")

    def test_the_player_never_loses_an_adventure_they_started(self):
        # begin Wychwood, then run many NPC days — it must stay the player's
        self.e.accept_quest("q_wychwood_vanishings")
        self.na.rng.seed(3)
        for day in range(1, 60):
            self.na.run_day(day)
        self.assertFalse(self.e.wychwood.is_resolved(),
                         "an NPC never resolves an adventure the player began")

    def test_state_round_trips(self):
        hero = self._strong_hero()
        self.na.active[hero.id] = {"adv": "emberfell", "act": 2, "day": 4}
        from engine.npc_adventuring import NpcAdventuringSystem
        na2 = NpcAdventuringSystem(self.e)
        na2.from_dict(self.na.to_dict())
        self.assertEqual(na2.active, self.na.active)


if __name__ == "__main__":
    unittest.main()
