"""The NPC production loop (P16.2): villages that make things."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine                # noqa: E402
from engine import production as pr                       # noqa: E402
from engine.production_loop import ProductionSystem, STORE_CAP  # noqa: E402


class TestProductionLoop(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.ps = self.engine.production

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    # ---- settlement identification ---------------------------------

    def test_only_real_towns_are_settlements(self):
        names = [s.name for s in self.ps._settlements()]
        self.assertTrue(names, "there should be at least one settlement")
        # a building that merely carries the word (Village Well) is not one
        for n in names:
            self.assertNotIn(n, self.engine.interiors,
                             f"{n} is a building, not a town")

    def test_producers_are_class_mapped_professions(self):
        by = self.ps._producers_by_settlement(self.ps._settlements())
        profs = {p for d in by.values() for p in d}
        self.assertTrue(profs, "some NPC should map to a profession")
        for p in profs:
            self.assertIn(p, pr.all_professions())

    # ---- gather / craft (controlled) -------------------------------

    def test_a_gatherer_fills_the_larder(self):
        store = {}
        self.ps._work(pr, store, {"woodcutter": [object()]})
        self.assertGreater(store.get("logs", 0), 0)

    def test_a_crafter_turns_inputs_into_goods(self):
        store = {"raw_trout": 10}
        made = self.ps._work(pr, store, {"cook": [object()]})
        self.assertGreater(made.get("cooked_trout", 0), 0)
        self.assertLess(store["raw_trout"], 10, "the catch was consumed")

    def test_a_crafter_makes_nothing_without_inputs(self):
        store = {}
        made = self.ps._work(pr, store, {"cook": [object()]})
        self.assertEqual(made, {})

    def test_the_larder_respects_its_cap(self):
        store = {}
        for _ in range(80):
            self.ps._work(pr, store, {"woodcutter": [object()] * 5})
        self.assertLessEqual(store.get("logs", 0), STORE_CAP)

    # ---- the daily step over time ----------------------------------

    def test_villages_produce_over_a_week(self):
        for _ in range(8):
            self.ps.run_day()
        total = sum(sum(s.values()) for s in self.ps.stores.values())
        self.assertGreater(total, 0, "the economy made something")

    def test_run_day_never_raises_and_returns_lines(self):
        out = self.ps.run_day()
        self.assertIsInstance(out, list)

    # ---- persistence ------------------------------------------------

    def test_stores_round_trip(self):
        self.ps.stores = {"Oakvale Village": {"logs": 12, "cooked_trout": 3}}
        clone = ProductionSystem(self.engine)
        clone.from_dict(self.ps.to_dict())
        self.assertEqual(clone.stores, self.ps.stores)

    def test_stores_survive_save_load(self):
        for _ in range(6):
            self.ps.run_day()
        before = {k: dict(v) for k, v in self.ps.stores.items()}
        self.assertTrue(any(before.values()), "there is something to save")
        self.engine.save_game(name="p162_roundtrip")
        e2 = GameEngine(llm_provider="heuristic",
                        enable_npc_processes=False)
        e2.start_game()
        self.assertTrue(e2.load_game(name="p162_roundtrip"))
        self.assertEqual(e2.production.stores, before)
        e2.end_game()


class TestConsumption(unittest.TestCase):
    """T2.4 — a settlement eats its provisions; hunger pushes a real shortage."""

    def test_consume_eats_food_and_reports_hunger(self):
        from engine.production_loop import ProductionSystem
        ps = ProductionSystem.__new__(ProductionSystem)
        store = {"bread": 3, "meat": 2, "ore": 10}
        # 8 people eat ~4 units — 5 food covers it (not hungry); food eaten first
        self.assertFalse(ps._consume(store, {"f": list(range(8))}))
        self.assertNotIn("bread", store, "bread eaten first")
        self.assertEqual(store["ore"], 10, "non-food untouched")
        # a scarce larder goes hungry
        scarce = {"bread": 1}
        self.assertTrue(ps._consume(scarce, {"f": list(range(10))}))
        self.assertEqual(scarce, {}, "the larder is emptied")

    def test_hungry_town_declares_a_shortage(self):
        from engine.game_engine import GameEngine
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        e.production._maybe_shortage()
        self.assertIn("bread", e.world_director.shortages,
                      "a hungry town pushes a food shortage (radiant reads it)")
        e.end_game()


if __name__ == "__main__":
    unittest.main()
