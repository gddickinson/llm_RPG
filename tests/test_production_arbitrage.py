"""Merchant arbitrage (P16.2b): a caravan carries a settlement's glut of a
good to where it's scarce — plenty flows to want, night after night."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from engine.production_loop import (ProductionSystem, CARAVAN_LOAD,
                                    CARAVAN_MIN_GAP)


class TestArbitrage(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.prod = ProductionSystem(self.engine, seed=1)
        self.setts = self.prod._settlements()
        if len(self.setts) < 2:
            self.skipTest("need two settlements to trade between")
        self.a, self.b = self.setts[0], self.setts[1]

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_a_glut_flows_to_scarcity(self):
        self.prod.store_of(self.a.name)["cooked_fish"] = 20
        self.prod.store_of(self.b.name)["cooked_fish"] = 0
        moves = self.prod._arbitrage(self.setts)
        self.assertTrue(any(m[0] == "cooked_fish" for m in moves))
        self.assertLess(self.prod.store_of(self.a.name)["cooked_fish"], 20)
        self.assertGreater(self.prod.store_of(self.b.name)["cooked_fish"], 0)

    def test_the_caravan_load_is_bounded(self):
        self.prod.store_of(self.a.name)["bread"] = 40
        self.prod.store_of(self.b.name)["bread"] = 0
        self.prod._arbitrage(self.setts)
        self.assertEqual(self.prod.store_of(self.b.name)["bread"],
                         CARAVAN_LOAD, "one caravan-load a day")

    def test_a_small_gap_moves_nothing(self):
        self.prod.store_of(self.a.name)["ale"] = CARAVAN_MIN_GAP - 1
        self.prod.store_of(self.b.name)["ale"] = 0
        moves = self.prod._arbitrage(self.setts)
        self.assertFalse(any(m[0] == "ale" for m in moves),
                         "not worth a caravan")

    def test_nothing_is_created_or_lost(self):
        self.prod.store_of(self.a.name)["potion"] = 30
        self.prod.store_of(self.b.name)["potion"] = 2
        total0 = sum(self.prod.store_of(s.name).get("potion", 0)
                     for s in self.setts)
        self.prod._arbitrage(self.setts)
        total1 = sum(self.prod.store_of(s.name).get("potion", 0)
                     for s in self.setts)
        self.assertEqual(total0, total1, "the caravan carries, never mints")

    def test_needs_two_settlements(self):
        self.prod.store_of(self.a.name)["bread"] = 50
        self.assertEqual(self.prod._arbitrage([self.a]), [])

    def test_deterministic(self):
        for st in (self.prod.store_of(self.a.name),
                   self.prod.store_of(self.b.name)):
            st.clear()
        self.prod.store_of(self.a.name)["cooked_fish"] = 25
        m1 = self.prod._arbitrage(self.setts)
        # reset and repeat
        self.prod.store_of(self.a.name)["cooked_fish"] = 25
        self.prod.store_of(self.b.name)["cooked_fish"] = 0
        m2 = self.prod._arbitrage(self.setts)
        self.assertEqual(m1, m2)

    def test_run_day_redistributes(self):
        self.prod.store_of(self.a.name)["cooked_fish"] = 30
        self.prod.store_of(self.b.name)["cooked_fish"] = 0
        self.prod.run_day()
        self.assertGreater(self.prod.store_of(self.b.name)["cooked_fish"], 0,
                           "the daily loop runs the caravans")


if __name__ == "__main__":
    unittest.main()
