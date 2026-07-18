"""M6 — the cross-game BLUEPRINT library (`engine/blueprint_library`): save a
build design, reload it in any game and stamp it anywhere. Uses a tmp library
root so the real `data/dm_library` is untouched.
"""

import os
import tempfile
import unittest

os.environ["LLM_RPG_DM_LIBRARY"] = tempfile.mkdtemp(prefix="llmrpg_bp_")

from engine import blueprint_library as bl


class TestSpec(unittest.TestCase):
    def test_plan_normalises_to_offsets(self):
        plan = {(10, 10): "building", (11, 10): "building", (11, 11): "road"}
        spec = bl.plan_to_spec(plan, "Keep")
        self.assertEqual(spec["name"], "Keep")
        self.assertIn([0, 0, "building"], spec["tiles"])
        self.assertIn([1, 1, "road"], spec["tiles"])
        self.assertEqual((spec["w"], spec["h"]), (2, 2))

    def test_stamp_anchors_anywhere(self):
        spec = bl.plan_to_spec({(3, 3): "road", (3, 4): "building"}, "L")
        out = bl.stamp(spec, 50, 50)
        self.assertEqual(out[(50, 50)], "road")
        self.assertEqual(out[(50, 51)], "building")


class TestLibrary(unittest.TestCase):
    def setUp(self):
        os.environ["LLM_RPG_DM_LIBRARY"] = tempfile.mkdtemp(prefix="llmrpg_bp_")

    def test_save_and_list(self):
        self.assertEqual(bl.count(), 0)
        bl.save_blueprint("Fort", {(0, 0): "building", (1, 0): "building"}, "")
        self.assertEqual(bl.count(), 1)
        self.assertIn("Fort", [n for _, n, _ in bl.list_blueprints()])

    def test_empty_plan_refused(self):
        msg = bl.save_blueprint("Nothing", {}, "")
        self.assertIn("Nothing planned", msg)
        self.assertEqual(bl.count(), 0)

    def test_reload_stamps_the_pattern(self):
        bl.save_blueprint("Road", {(5, 5): "road", (6, 5): "road"}, "")
        _bid, name, spec = bl.list_blueprints()[0]     # a "new game" re-reads it
        stamped = bl.stamp(spec, 20, 20)
        self.assertEqual(name, "Road")
        self.assertEqual(set(stamped.values()), {"road"})
        self.assertEqual(len(stamped), 2)

    def test_unique_ids_for_same_name(self):
        bl.save_blueprint("Wall", {(0, 0): "building"}, "")
        bl.save_blueprint("Wall", {(0, 0): "building"}, "")
        self.assertEqual(bl.count(), 2)


class TestPlannerIntegration(unittest.TestCase):
    def setUp(self):
        os.environ["LLM_RPG_DM_LIBRARY"] = tempfile.mkdtemp(prefix="llmrpg_bp_")
        try:
            import pygame
            pygame.init()
        except Exception:
            self.skipTest("pygame missing")
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        from ui.build_planner import BuildPlanner
        self.bp = BuildPlanner(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_save_then_load_repopulates_the_plan(self):
        self.bp.plan = {(self.bp.cx, self.bp.cy): "building"}
        self.bp._save_blueprint()
        self.assertEqual(bl.count(), 1)
        self.bp.plan = {}
        self.bp._load_blueprint()
        self.assertEqual(len(self.bp.plan), 1)
        self.assertIn("building", self.bp.plan.values())


if __name__ == "__main__":
    unittest.main()
