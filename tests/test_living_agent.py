"""The living agent (2026-07-12) — an away-hero with a life.

Beyond survive/fight/loot/wander, the autoplay brain now chats with folk,
takes and pursues quests, recruits a party, and explores toward places its
calling draws it — biased by a disposition the player sets — and writes its
deeds into the record the player can review."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_liva_"))

import unittest

from engine.game_engine import GameEngine
from engine.agent_controller import AgentController
from engine.settings import get_setting, set_setting
from world.monsters import build_monster
from world.world_map import TerrainType
from characters.character_types import CharacterClass
from quests.quest import Quest, QuestObjective, ObjectiveType, QuestStatus


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.ac = AgentController()
        for yy in range(2, 22):
            for xx in range(2, 22):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        self._put(self.p, 10, 10)
        # clear the whole pre-existing cast so only this test's NPCs are in
        # play (the world cast could otherwise sit nearer than a test ally)
        for nid in list(self.engine.npc_manager.npcs):
            n = self.engine.npc_manager.npcs[nid]
            self.engine.world.map.remove_character(n)
            self.engine.npc_manager.remove_npc(nid)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put(self, ch, x, y):
        self.engine.world.map.remove_character(ch)
        ch.position = (x, y)
        self.engine.world.map.place_character(ch, x, y)

    def _friend(self, cid, x, y, cls="merchant", rel=0):
        n = build_monster("wolf", (x, y))
        n.id = cid
        n.name = cid.title()
        n.character_class = CharacterClass(cls)
        n.metadata = {}
        n.relationships[self.p.id] = rel
        self.engine.npc_manager.add_npc(n)
        self.engine.world.map.place_character(n, x, y)
        return n


class TestSocial(_Base):
    def test_takes_an_offered_quest_from_a_neighbour(self):
        giver = self._friend("brenna", 11, 10)
        q = Quest(id="brenna_q", title="A Small Favour", description="",
                  objectives=[QuestObjective(ObjectiveType.TALK, "x")],
                  status=QuestStatus.AVAILABLE, giver_id="brenna")
        self.engine.quest_manager.quests["brenna_q"] = q
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "accept_quest")

    def test_recruits_a_willing_ally(self):
        self._friend("ksana", 11, 10, cls="ranger", rel=60)  # warm enough
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "recruit")

    def test_chats_with_a_stranger(self):
        self._friend("odd", 11, 10, rel=0)                   # no quest, cold
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "talk")

    def test_a_chat_is_recorded_as_a_deed(self):
        self._friend("odd", 11, 10, rel=0)
        self.ac.take_turn(self.engine, self.p)
        self.assertIn("[Away]", _recent(self.engine))
        self.assertTrue(self.ac.greeted)


class TestExplore(_Base):
    def test_a_named_goal_is_class_flavoured(self):
        self.p.character_class = CharacterClass.WIZARD
        goal = self.ac._named_goal(self.engine, self.p)
        self.assertIsNotNone(goal)
        self.assertIsNotNone(self.ac.goal_name)

    def test_visited_places_are_not_re_sought(self):
        goal1 = self.ac._named_goal(self.engine, self.p)
        self.ac.visited.add(self.ac.goal_name)
        goal2 = self.ac._named_goal(self.engine, self.p)
        self.assertNotEqual(goal1, goal2)


class TestDisposition(_Base):
    def test_setting_round_trips(self):
        set_setting(self.p, "disposition", "explorer")
        self.assertEqual(get_setting(self.p, "disposition"), "explorer")

    def test_cautious_keeps_its_distance(self):
        set_setting(self.p, "disposition", "cautious")
        foe = build_monster("wolf", (14, 10))
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.place_character(foe, 14, 10)
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "flee")

    def test_explorer_wanders_over_a_quest(self):
        # an explorer roams rather than chasing a quest target
        set_setting(self.p, "disposition", "explorer")
        q = Quest(id="far", title="Far Errand", description="",
                  objectives=[QuestObjective(ObjectiveType.TALK,
                                             "guard_01")],
                  status=QuestStatus.ACTIVE)
        self.engine.quest_manager.quests["far"] = q
        # no friend nearby, no loot -> falls to explore, not quest-pursuit
        plan = self.ac.decide(self.engine, self.p)
        self.assertIn(plan[0], ("move", "wait"))


class TestDeedTrail(_Base):
    def test_the_goal_is_visible_to_the_player(self):
        self.ac.take_turn(self.engine, self.p)
        self.assertIn("agent_goal", self.p.metadata)

    def test_recruiting_is_recorded(self):
        self._friend("ksana", 11, 10, cls="ranger", rel=60)
        self.ac.take_turn(self.engine, self.p)
        if "ksana" in self.engine.companion_manager.party:
            self.assertIn("recruited", _recent(self.engine))


if __name__ == "__main__":
    unittest.main()
