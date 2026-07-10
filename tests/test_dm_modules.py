"""Adventure module tests (P6.5) — atomicity above all."""

import unittest

from engine.game_engine import GameEngine
from engine.dm_modules import prevalidate, install_module


def _module(engine, mid="rot_court"):
    px, py = engine.player.position
    far = [px + 25, py + 25]
    return {
        "module_id": mid,
        "title": "The Rot Court",
        "announcement": "They say the fen has crowned a king of rot.",
        "monsters": {
            "rotling": {"name": "Rotling", "class": "monster",
                        "race": "goblin", "hp": 6, "level": 1,
                        "symbol": "r"}},
        "items": {
            "rot_crown": {"name": "Crown of Rot", "item_type": "misc",
                          "value": 120, "rarity": "rare"}},
        "spawns": [{"template_id": "rotling", "position": far}],
        "placements": [{"item_id": "rot_crown", "position": far}],
        "quests": {
            "q_rot_court": {
                "title": "The Rot Court",
                "description": "End the court before it crowns more.",
                "objectives": [{"type": "kill", "target": "monster",
                                "required": 1,
                                "description": "Destroy a Rotling"}],
                "giver_id": "hamlet_priest_01",
                "reward_gold": 40, "reward_xp": 90}},
        "beats": [{"day_offset": 2, "command": "narrate",
                   "args": {"text": "The rot spreads."}}],
    }


class TestDMModules(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        MONSTER_TEMPLATES.pop("rotling", None)
        ITEM_REGISTRY.pop("rot_crown", None)
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_full_module_installs(self):
        module = _module(self.engine)
        ok, note = self.engine.dm.install_module(module)
        self.assertTrue(ok, note)
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        self.assertIn("rotling", MONSTER_TEMPLATES)
        self.assertIn("rot_crown", ITEM_REGISTRY)
        self.assertIsNotNone(
            self.engine.quest_manager.get("q_rot_court"))
        self.assertTrue(any(n.name == "Rotling"
                            for n in
                            self.engine.npc_manager.npcs.values()))
        self.assertTrue(self.engine.dm.scheduled)
        self.assertIn("crowned a king of rot",
                      " ".join(self.engine.world_director.rumors))

    def test_prevalidation_blocks_bad_modules_completely(self):
        module = _module(self.engine)
        module["monsters"]["rotling"]["level"] = \
            self.engine.player.level + 10   # over cap
        budget_before = self.engine.dm.budget_remaining()
        ok, note = self.engine.dm.install_module(module)
        self.assertFalse(ok)
        self.assertIn("level cap", note)
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        self.assertNotIn("rotling", MONSTER_TEMPLATES)
        self.assertNotIn("rot_crown", ITEM_REGISTRY)
        self.assertIsNone(self.engine.quest_manager.get("q_rot_court"))
        self.assertEqual(self.engine.dm.budget_remaining(),
                         budget_before, "nothing may be charged")

    def test_midway_failure_rolls_back_everything(self):
        module = _module(self.engine, mid="rollback_test")
        dm = self.engine.dm
        original = dm.create_quest
        dm.create_quest = lambda *a, **k: dm._log(
            "create_quest", False, "injected failure")
        try:
            budget_before = dm.budget_remaining()
            ok, note = install_module(self.engine, module)
            self.assertFalse(ok)
            self.assertIn("rolled back", note)
            from world.monsters import MONSTER_TEMPLATES
            from items.item_registry import ITEM_REGISTRY
            self.assertNotIn("rotling", MONSTER_TEMPLATES,
                             "defined monster must be rolled back")
            self.assertNotIn("rot_crown", ITEM_REGISTRY)
            self.assertFalse(any(n.name == "Rotling" for n in
                                 self.engine.npc_manager.npcs.values()),
                             "spawn must be rolled back")
            self.assertEqual(dm.budget_remaining(), budget_before,
                             "budget must be refunded")
        finally:
            dm.create_quest = original

    def test_budget_gate(self):
        for _ in range(11):
            self.engine.dm.adjust_faction("villagers", 1)
        problems = prevalidate(self.engine, _module(self.engine))
        self.assertTrue(any("budget" in p for p in problems))

    def test_bridge_can_install_module(self):
        import json
        import os
        import shutil
        import tempfile
        from engine.dm_bridge import DMBridge
        tmp = tempfile.mkdtemp()
        try:
            bridge = DMBridge(self.engine, root=tmp)
            with open(os.path.join(tmp, "inbox", "m.json"), "w") as fp:
                json.dump({"commands": [
                    {"command": "install_module",
                     "args": {"module": _module(self.engine)}}]}, fp)
            bridge.poll()
            with open(os.path.join(tmp, "processed",
                                   "m.result.json")) as fp:
                results = json.load(fp)["results"]
            self.assertTrue(results[0]["ok"], results)
            self.assertIsNotNone(
                self.engine.quest_manager.get("q_rot_court"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_notebook_records_the_module(self):
        self.engine.dm.install_module(_module(self.engine))
        entries = [e for e in self.engine.dm.notebook
                   if e["command"] == "install_module" and e["ok"]]
        self.assertTrue(entries)
        self.assertIn("The Rot Court", entries[-1]["note"])


if __name__ == "__main__":
    unittest.main()
