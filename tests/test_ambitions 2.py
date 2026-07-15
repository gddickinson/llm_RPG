"""Ambitions that drive action (P20.1).

An NPC's goal string is matched to an ambition (wealth / romance / mastery
/ vengeance / escape); nightly it makes progress, and on reaching its goal
the ambition is REALISED with a real effect and a [Realm] beat — a
merchant prospers, two souls become sweethearts, a crafter is hailed a
master. State lives on the NPC's metadata, so it rides the save."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_amb_"))

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from characters.character_types import CharacterClass


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.A = self.engine.ambitions
        self.A.rng.seed(0)
        self.cats = self.A._categories()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _npc(self, goals, cid, cls="merchant"):
        m = build_monster("wolf", (5, 5))
        m.id = cid
        m.name = cid.title()
        m.goals = list(goals)
        m.character_class = CharacterClass(cls)
        m.metadata = {}
        self.engine.npc_manager.add_npc(m)
        return m


class TestClassification(_Base):
    def test_wealth_goal(self):
        n = self._npc(["Earn enough gold to retire comfortably"], "greta")
        self.assertEqual(self.A._ambition_of(n, self.cats), "wealth")

    def test_romance_goal(self):
        n = self._npc(["Find romance or companionship"], "rowan")
        self.assertEqual(self.A._ambition_of(n, self.cats), "romance")

    def test_mastery_goal(self):
        n = self._npc(["Advance in rank"], "kell", cls="guard")
        self.assertEqual(self.A._ambition_of(n, self.cats), "mastery")

    def test_a_duty_is_no_personal_ambition(self):
        n = self._npc(["Protect the village", "Bless travelers"], "anselm",
                      cls="cleric")
        self.assertIsNone(self.A._ambition_of(n, self.cats))

    def test_classification_is_cached(self):
        n = self._npc(["Make a profit"], "goren")
        self.A._ambition_of(n, self.cats)
        self.assertEqual(n.metadata.get("ambition"), "wealth")


class TestProgressAndAchievement(_Base):
    def test_progress_accrues(self):
        n = self._npc(["Earn coin"], "vera")
        self.A.run_day()
        self.assertGreater(n.metadata.get("ambition_progress", 0), 0)

    def test_reaching_the_goal_realises_it(self):
        n = self._npc(["Earn enough gold to retire comfortably"], "goren")
        for _ in range(15):
            self.A.run_day()
        self.assertTrue(n.metadata.get("ambition_done"))
        self.assertEqual(n.metadata.get("realised_ambition"), "wealth")

    def test_a_realised_ambition_is_announced(self):
        n = self._npc(["Earn enough gold to retire comfortably"], "goren")
        for _ in range(15):
            self.A.run_day()
        self.assertIn("prospered", _recent(self.engine))

    def test_a_done_ambition_does_not_re_fire(self):
        n = self._npc(["Earn coin"], "goren")
        for _ in range(15):
            self.A.run_day()
        self.assertTrue(n.metadata.get("ambition_done"))
        gold = n.gold
        prog = n.metadata.get("ambition_progress")
        self.A.run_day()
        self.assertEqual(n.gold, gold)
        self.assertEqual(n.metadata.get("ambition_progress"), prog)


class TestEffects(_Base):
    def test_wealth_prospers(self):
        n = self._npc(["Make a profit"], "goren")
        g0 = n.gold
        self.A._achieve(n, "wealth")
        self.assertTrue(n.metadata.get("prospered"))
        self.assertGreater(n.gold, g0)

    def test_mastery_masters(self):
        n = self._npc(["Learn a new craft or skill"], "alric")
        self.A._achieve(n, "mastery")
        self.assertTrue(n.metadata.get("master"))

    def test_romance_forms_a_couple(self):
        one = self._npc(["Find romance or companionship"], "rowan")
        # give it a definite partner-to-be in the pool
        two = self._npc(["Keep the ale flowing"], "brann", cls="merchant")
        self.A._do_romance(one)
        partner = one.metadata.get("partner")
        self.assertIsNotNone(partner, "an emergent couple forms")
        other = self.engine.npc_manager.get_npc(partner)
        self.assertEqual(other.metadata.get("partner"), one.id, "mutual")
        self.assertGreater(one.get_relationship(partner), 0)


class TestSkips(_Base):
    def test_player_characters_are_skipped(self):
        n = self._npc(["Earn coin"], "hero")
        n.metadata["player_char"] = True
        self.A.run_day()
        self.assertIsNone(n.metadata.get("ambition_progress"))


if __name__ == "__main__":
    unittest.main()
