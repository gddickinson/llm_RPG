"""DM define_structure tests (P9.6) — towers that outlive campaigns."""

import unittest

from engine.game_engine import GameEngine


def _spec(attach="Old Farmhouse"):
    return {
        "attach_to": attach,
        "levels": [
            {"name": "DM Folly — Hall",
             "description": "A hall that wasn't here yesterday.",
             "grid": ["WWWWWWW",
                      "WF.K.<W",
                      "WWWDWWW"],
             "inscriptions": ["The DM was here."]},
            {"name": "DM Folly — Attic",
             "position": "above",
             "grid": ["WWWWWWW",
                      "WF...>W",
                      "WWWWWWW"],
             "monsters": [{"template": "goblin", "at": [2, 1]}],
             "chest_loot": []},
        ],
    }


class TestDMStructures(unittest.TestCase):
    def setUp(self):
        from tests import clean_dm_library
        clean_dm_library()
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.dm = self.engine.dm

    def tearDown(self):
        from world.structures import STRUCTURES
        for sid in list(self.dm.defined_structures):
            STRUCTURES.pop(sid, None)
        STRUCTURES.pop("dm_folly", None)
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_define_and_enter(self):
        ok, note = self.dm.define_structure("dm_folly", _spec())
        self.assertTrue(ok, note)
        inter = self.engine.interiors.get("Old Farmhouse")
        self.assertIsNotNone(inter)
        self.assertIn("Folly", inter.name)
        self.assertIsNotNone(inter.level_above, "the attic exists")

    def test_charter_level_cap(self):
        spec = _spec()
        spec["levels"] = spec["levels"] * 3   # 6 levels
        ok, note = self.dm.define_structure("dm_folly", spec)
        self.assertFalse(ok)
        self.assertIn("charter", note)

    def test_charter_grid_cap(self):
        spec = _spec()
        spec["levels"][0]["grid"] = ["W" * 20] * 3
        ok, note = self.dm.define_structure("dm_folly", spec)
        self.assertFalse(ok)
        self.assertIn("16x12", note)

    def test_unknown_monster_refused(self):
        spec = _spec()
        spec["levels"][1]["monsters"] = [
            {"template": "tarrasque", "at": [2, 1]}]
        ok, note = self.dm.define_structure("dm_folly", spec)
        self.assertFalse(ok)
        self.assertIn("unknown monster", note)

    def test_nowhere_to_attach_refused(self):
        ok, note = self.dm.define_structure(
            "dm_folly", _spec(attach="The Moon"))
        self.assertFalse(ok)
        self.assertIn("no place", note)

    def test_budget_charged(self):
        before = self.dm.budget_remaining()
        self.dm.define_structure("dm_folly", _spec())
        self.assertEqual(self.dm.budget_remaining(), before - 1)

    def test_definitions_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        from world.structures import STRUCTURES
        self.dm.define_structure("dm_folly", _spec())
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="folly")
            STRUCTURES.pop("dm_folly", None)
            self.dm.defined_structures = {}
            self.assertTrue(sm.load(self.engine, name="folly"))
            self.assertIn("dm_folly",
                          self.engine.dm.defined_structures)
            self.assertIn("dm_folly", STRUCTURES)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_legendarium_inherits_across_campaigns(self):
        """George's compounding world: the folly outlives the game."""
        from world.structures import STRUCTURES
        self.dm.define_structure("dm_folly", _spec())
        STRUCTURES.pop("dm_folly", None)      # simulate fresh boot
        engine2 = GameEngine(llm_provider="heuristic",
                             enable_npc_processes=False)
        engine2.start_game()
        try:
            self.assertIn("dm_folly", STRUCTURES,
                          "new campaigns inherit DM structures")
        finally:
            engine2.end_game()

    def test_bridge_allows_the_command(self):
        from engine.dm_bridge import ALLOWED_COMMANDS
        self.assertIn("define_structure", ALLOWED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
