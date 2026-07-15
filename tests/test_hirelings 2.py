"""Hirelings (M.7) — party members you PAY.

A signing fee then a daily wage; they serve a fixed term or an open salary
and walk when the coin stops (souring after a day's grace). The whole
contract lives on npc.metadata, so a hireling rides the save.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_hire_"))

import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager
from world.monsters import build_monster
from characters.character_types import CharacterClass


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.H = self.engine.hirelings
        self.p = self.engine.player
        self.p.gold = 500

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _merc(self, cid="blade", cls="warrior", level=3):
        n = build_monster("wolf", (self.p.position[0] + 1, self.p.position[1]))
        n.id = cid
        n.name = cid.title()
        n.character_class = CharacterClass(cls)
        n.level = level
        n.metadata = {}
        self.engine.npc_manager.add_npc(n)
        self.engine.world.map.place_character(n, *n.position)
        return n

    def _day(self):
        return self.engine.world.time // (24 * 60)


class TestHiring(_Base):
    def test_hire_a_blade_for_coin(self):
        m = self._merc()
        sign, wage = self.H.cost(m)
        gold0 = self.p.gold
        self.assertEqual(self.H.can_hire(m), "")
        self.H.hire("blade")
        self.assertIn("blade", self.engine.companion_manager.party)
        self.assertTrue(self.H.is_hireling(m))
        self.assertEqual(self.p.gold, gold0 - sign)

    def test_no_coin_no_blade(self):
        m = self._merc()
        self.p.gold = 0
        self.assertNotEqual(self.H.can_hire(m), "")
        self.H.hire("blade")
        self.assertNotIn("blade", self.engine.companion_manager.party)

    def test_a_villager_is_no_hireling(self):
        m = self._merc(cls="villager")
        self.assertNotEqual(self.H.can_hire(m), "")


class TestWages(_Base):
    def test_the_daily_wage_is_drawn(self):
        m = self._merc()
        self.H.hire("blade")
        gold = self.p.gold
        _, wage = self.H.cost(m)
        self.H.run_day(self._day() + 1)
        self.assertEqual(self.p.gold, gold - wage)
        self.assertEqual(m.metadata["hire"]["paid_through"], self._day() + 1)

    def test_a_term_contract_ends_itself(self):
        self._merc("scout")
        self.H.hire("scout", days=2)
        self.H.run_day(self._day() + 2)
        self.assertNotIn("scout", self.engine.companion_manager.party)

    def test_unpaid_hireling_grumbles_then_walks(self):
        m = self._merc()
        self.H.hire("blade")
        d = self._day()
        self.p.gold = 0
        rel0 = m.get_relationship(self.p.id)
        self.H.run_day(d + 1)                      # 1 missed — grace
        self.assertIn("blade", self.engine.companion_manager.party)
        self.H.run_day(d + 2)                      # 2 missed — walks, sours
        self.assertNotIn("blade", self.engine.companion_manager.party)
        self.assertFalse(self.H.is_hireling(m))
        self.assertLess(m.get_relationship(self.p.id), rel0)


class TestPersistence(_Base):
    def test_a_hireling_rides_the_save(self):
        self._merc()
        self.H.hire("blade")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="h")
            eng2 = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
            sm.load(eng2, name="h")
            self.assertIn("blade", eng2.companion_manager.party)
            m2 = eng2.npc_manager.get_npc("blade")
            self.assertTrue(eng2.hirelings.is_hireling(m2))
            eng2.end_game()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCommand(_Base):
    def test_the_hire_command_parses_a_term(self):
        from engine.hirelings import HirelingSystem
        self.assertIsNone(HirelingSystem.parse_days("/hire"))
        self.assertEqual(HirelingSystem.parse_days("/hire 5"), 5)


if __name__ == "__main__":
    unittest.main()
