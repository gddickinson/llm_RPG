"""Module pack tests (P1.4) — authored campaign packs as data."""

import json
import os
import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine


def _pack(mid="pk_test", quest_id="q_pk_test"):
    return {
        "module_id": mid,
        "title": "The Test Pack",
        "announcement": "A test light wanders the wilds.",
        "monsters": {
            "pk_stalker": {"name": "Pack Stalker", "class": "monster",
                           "race": "goblin", "hp": 8, "level": 2,
                           "symbol": "k"}},
        "items": {
            "pk_lantern": {"name": "Pack Lantern", "item_type": "misc",
                           "value": 40}},
        "spawns": [{"template_id": "pk_stalker",
                    "anchor": "wilderness"}],
        "placements": [{"item_id": "pk_lantern",
                        "anchor": "wilderness"}],
        "quests": {
            quest_id: {
                "title": "The Test Pack",
                "description": "Put the test light out.",
                "objectives": [{"type": "kill", "target": "monster",
                                "required": 1,
                                "description": "Slay the stalker"}],
                "giver_id": "guard_01",
                "reward_gold": 30, "reward_xp": 50}},
        "beats": [{"day_offset": 2, "command": "narrate",
                   "args": {"text": "The light returns."}}],
    }


class TestModulePacks(unittest.TestCase):
    def setUp(self):
        from tests import clean_dm_library
        clean_dm_library()
        self.tmp = tempfile.mkdtemp()
        self._prev = os.environ.get("LLM_RPG_MODULE_PACKS")
        os.environ["LLM_RPG_MODULE_PACKS"] = self.tmp
        with open(os.path.join(self.tmp, "pk_test.json"), "w") as fp:
            json.dump(_pack(), fp)
        self.engine = None

    def _boot(self):
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        return engine

    def tearDown(self):
        if self._prev is not None:
            os.environ["LLM_RPG_MODULE_PACKS"] = self._prev
        else:
            os.environ.pop("LLM_RPG_MODULE_PACKS", None)
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        MONSTER_TEMPLATES.pop("pk_stalker", None)
        ITEM_REGISTRY.pop("pk_lantern", None)
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self.engine is not None:
            try:
                self.engine.end_game()
            except Exception:
                pass

    def test_pack_installs_on_new_game(self):
        self.engine = self._boot()
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        self.assertIn("pk_stalker", MONSTER_TEMPLATES)
        self.assertIn("pk_lantern", ITEM_REGISTRY)
        self.assertIsNotNone(
            self.engine.quest_manager.get("q_pk_test"))
        self.assertTrue(any(n.name == "Pack Stalker" for n in
                            self.engine.npc_manager.npcs.values()))
        self.assertIn("A test light wanders the wilds.",
                      self.engine.world_director.rumors)
        self.assertTrue(self.engine.dm.scheduled)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("[Module]", log)

    def test_budget_not_charged(self):
        self.engine = self._boot()
        from engine.dm_api import MUTATION_BUDGET
        self.assertEqual(self.engine.dm.budget_remaining(),
                         MUTATION_BUDGET,
                         "authored packs must not eat the DM's day")

    def test_anchor_respects_the_charter_distance(self):
        self.engine = self._boot()
        px, py = self.engine.player.position
        stalker = next(n for n in
                       self.engine.npc_manager.npcs.values()
                       if n.name == "Pack Stalker")
        sx, sy = stalker.position
        self.assertGreaterEqual(abs(sx - px) + abs(sy - py), 6)

    def test_second_campaign_tolerates_inherited_definitions(self):
        """Definitions persist (registries + Legendarium); the pack's
        world effects must still land in every new campaign."""
        self.engine = self._boot()
        engine2 = self._boot()
        try:
            self.assertIsNotNone(
                engine2.quest_manager.get("q_pk_test"),
                "pack quest must exist in the second campaign too")
            self.assertTrue(any(n.name == "Pack Stalker" for n in
                                engine2.npc_manager.npcs.values()))
        finally:
            engine2.end_game()

    def test_corrupt_pack_never_blocks_boot(self):
        with open(os.path.join(self.tmp, "aa_junk.json"), "w") as fp:
            fp.write("{not json")
        self.engine = self._boot()
        self.assertIsNotNone(
            self.engine.quest_manager.get("q_pk_test"),
            "good packs still install past a corrupt one")

    def test_charter_breaking_pack_refused_atomically(self):
        bad = _pack(mid="pk_bad", quest_id="q_pk_bad")
        bad["monsters"] = {"pk_titan": {
            "name": "Pack Titan", "class": "monster",
            "race": "troll", "hp": 99, "level": 40}}
        bad["spawns"] = [{"template_id": "pk_titan",
                          "anchor": "wilderness"}]
        with open(os.path.join(self.tmp, "zz_bad.json"), "w") as fp:
            json.dump(bad, fp)
        self.engine = self._boot()
        from world.monsters import MONSTER_TEMPLATES
        self.assertNotIn("pk_titan", MONSTER_TEMPLATES)
        self.assertIsNone(self.engine.quest_manager.get("q_pk_bad"))
        self.assertIsNotNone(
            self.engine.quest_manager.get("q_pk_test"))

    def test_shipped_packs_pass_the_validator(self):
        os.environ["LLM_RPG_MODULE_PACKS"] = os.path.join(
            "data", "module_packs")
        try:
            from items.validate_packs import check_module_packs
            self.assertEqual(check_module_packs(), [])
        finally:
            os.environ["LLM_RPG_MODULE_PACKS"] = self.tmp


if __name__ == "__main__":
    unittest.main()
