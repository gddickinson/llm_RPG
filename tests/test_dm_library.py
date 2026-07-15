"""Legendarium tests (P6.7) — creations compound across campaigns."""

import json
import os
import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine


class TestLegendarium(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._prev_lib = os.environ.get("LLM_RPG_DM_LIBRARY")
        os.environ["LLM_RPG_DM_LIBRARY"] = self.tmp
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        if self._prev_lib is not None:
            os.environ["LLM_RPG_DM_LIBRARY"] = self._prev_lib
        else:
            os.environ.pop("LLM_RPG_DM_LIBRARY", None)
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        for tid in ("lib_wraith", "lib_pendant"):
            MONSTER_TEMPLATES.pop(tid, None)
            ITEM_REGISTRY.pop(tid, None)
        shutil.rmtree(self.tmp, ignore_errors=True)
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _define_wraith(self, engine=None):
        return (engine or self.engine).dm.define_monster("lib_wraith", {
            "name": "The Pale Wraith", "class": "monster",
            "race": "goblin", "hp": 9, "level": 1, "symbol": "w",
            "description": "A grief given shape."})

    def test_definitions_written_with_provenance(self):
        ok, _ = self._define_wraith()
        self.assertTrue(ok)
        with open(os.path.join(self.tmp, "monsters.json")) as fp:
            lib = json.load(fp)
        self.assertIn("lib_wraith", lib)
        prov = lib["lib_wraith"]["provenance"]
        self.assertIn("day", prov)
        self.assertIn("date", prov)

    def test_new_campaign_inherits_the_library(self):
        """George's core requirement: creations outlive the campaign."""
        self._define_wraith()
        from world.monsters import MONSTER_TEMPLATES
        MONSTER_TEMPLATES.pop("lib_wraith", None)  # simulate fresh boot
        engine2 = GameEngine(llm_provider="heuristic",
                             enable_npc_processes=False)
        engine2.start_game()
        try:
            self.assertIn("lib_wraith", MONSTER_TEMPLATES,
                          "new games must inherit the grown world")
            ok, note = engine2.dm.spawn_npc(
                "lib_wraith",
                (engine2.player.position[0] + 20,
                 engine2.player.position[1] + 20))
            self.assertTrue(ok, note)
        finally:
            engine2.end_game()

    def test_no_duplicate_recording(self):
        self._define_wraith()
        from engine.dm_library import record_definition
        again = record_definition("monsters", "lib_wraith",
                                  {"name": "x"}, 0)
        self.assertFalse(again)
        with open(os.path.join(self.tmp, "monsters.json")) as fp:
            lib = json.load(fp)
        self.assertEqual(lib["lib_wraith"]["spec"]["name"],
                         "The Pale Wraith", "original spec kept")

    def test_slain_dm_creation_enters_the_legendarium(self):
        self._define_wraith()
        px, py = self.engine.player.position
        ok, _ = self.engine.dm.spawn_npc("lib_wraith", (px + 20, py))
        self.assertTrue(ok)
        wraith = next(n for n in self.engine.npc_manager.npcs.values()
                      if n.name == "The Pale Wraith")
        wraith.hp = 1
        wraith.position = (px + 1, py)
        for _ in range(40):
            self.engine.combat_system.player_attack(wraith.name)
            if not wraith.is_active():
                break
        self.assertFalse(wraith.is_active())
        from engine.dm_library import legendarium_tail
        legends = legendarium_tail()
        self.assertTrue(legends, "the fallen wraith must become legend")
        self.assertEqual(legends[-1]["name"], "The Pale Wraith")
        self.assertEqual(legends[-1]["slain_by"],
                         self.engine.player.name)

    def test_digest_carries_the_legendarium(self):
        from engine.dm_library import record_legend
        record_legend({"name": "Old Terror", "kind": "monster",
                       "story": "long dead", "slain_by": "someone",
                       "day": 3})
        digest = self.engine.dm.digest()
        self.assertTrue(any(l["name"] == "Old Terror"
                            for l in digest["dm"]["legendarium"]))

    def test_corrupt_library_never_crashes_startup(self):
        with open(os.path.join(self.tmp, "monsters.json"), "w") as fp:
            fp.write("{corrupt")
        from engine.dm_library import load_into_registries
        self.assertEqual(load_into_registries(), 0)


if __name__ == "__main__":
    unittest.main()
