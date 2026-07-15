"""Session-DM bridge tests (P6.3)."""

import json
import os
import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.dm_bridge import DMBridge


class TestDMBridge(unittest.TestCase):
    def setUp(self):
        from tests import clean_dm_library
        clean_dm_library()
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.tmp = tempfile.mkdtemp()
        self.bridge = DMBridge(self.engine, root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _drop(self, name, payload):
        with open(os.path.join(self.tmp, "inbox", name), "w") as fp:
            json.dump(payload, fp)

    def _result(self, name):
        path = os.path.join(self.tmp, "processed",
                            name[:-5] + ".result.json")
        with open(path) as fp:
            return json.load(fp)["results"]

    def test_digest_exported_on_startup(self):
        path = os.path.join(self.tmp, "digest.json")
        self.assertTrue(os.path.exists(path))
        with open(path) as fp:
            digest = json.load(fp)
        self.assertIn("player", digest)
        self.assertTrue(os.path.exists(
            os.path.join(self.tmp, "README.md")))

    def test_bundle_executes_and_archives(self):
        self._drop("001_scene.json", {"commands": [
            {"command": "narrate",
             "args": {"text": "Thunder rolls over the fen."}}]})
        handled = self.bridge.poll()
        self.assertEqual(handled, 1)
        results = self._result("001_scene.json")
        self.assertTrue(results[0]["ok"])
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("[DM] Thunder rolls", log)
        # Inbox empty, original archived
        self.assertEqual(os.listdir(
            os.path.join(self.tmp, "inbox")), [])
        self.assertIn("001_scene.json", os.listdir(
            os.path.join(self.tmp, "processed")))

    def test_multi_command_bundle_in_order(self):
        px, py = self.engine.player.position
        spot = [px + 20, py + 20]
        self._drop("002_setup.json", {"commands": [
            {"command": "define_item",
             "args": {"item_id": "dm_test_orb",
                      "spec": {"name": "Test Orb",
                               "item_type": "misc", "value": 20}}},
            {"command": "place_item",
             "args": {"item_id": "dm_test_orb", "position": spot}},
        ]})
        self.bridge.poll()
        results = self._result("002_setup.json")
        self.assertTrue(all(r["ok"] for r in results), results)
        items = self.engine.world.ground_items.get(tuple(spot), [])
        self.assertTrue(any(i.id == "dm_test_orb" for i in items))
        from items.item_registry import ITEM_REGISTRY
        ITEM_REGISTRY.pop("dm_test_orb", None)

    def test_charter_refusals_reported_not_crashed(self):
        px, py = self.engine.player.position
        self._drop("003_bad.json", {"commands": [
            {"command": "spawn_npc",
             "args": {"template_id": "wolf",
                      "position": [px + 1, py]}}]})
        self.bridge.poll()
        results = self._result("003_bad.json")
        self.assertFalse(results[0]["ok"])
        self.assertIn("charter", results[0]["note"])

    def test_unknown_and_forbidden_commands_refused(self):
        self._drop("004_evil.json", {"commands": [
            {"command": "to_dict", "args": {}},
            {"command": "run_scheduled", "args": {}},
            {"command": "fireball_the_player", "args": {}}]})
        self.bridge.poll()
        results = self._result("004_evil.json")
        self.assertTrue(all(not r["ok"] for r in results))

    def test_malformed_json_never_crashes(self):
        with open(os.path.join(self.tmp, "inbox", "005_junk.json"),
                  "w") as fp:
            fp.write("{this is not json")
        handled = self.bridge.poll()
        self.assertEqual(handled, 1)
        results = self._result("005_junk.json")
        self.assertFalse(results[0]["ok"])
        self.assertIn("unreadable", results[0]["note"])

    def test_bad_args_reported(self):
        self._drop("006_args.json", {"commands": [
            {"command": "narrate", "args": {"wrong_kwarg": 1}}]})
        self.bridge.poll()
        results = self._result("006_args.json")
        self.assertFalse(results[0]["ok"])
        self.assertIn("bad args", results[0]["note"])

    def test_digest_refreshes_after_bundles(self):
        self._drop("007_gold.json", {"commands": [
            {"command": "narrate", "args": {"text": "A star falls."}}]})
        self.bridge.poll()
        with open(os.path.join(self.tmp, "digest.json")) as fp:
            digest = json.load(fp)
        self.assertTrue(any("A star falls." in str(e)
                            for e in digest["recent_events"]))


if __name__ == "__main__":
    unittest.main()
