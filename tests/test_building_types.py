"""Building-type catalog & room classification (P16.3)."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from world import building_types as bt                    # noqa: E402
from world.interiors import Interior                      # noqa: E402


class TestCatalogue(unittest.TestCase):
    def test_kinds_and_professions(self):
        self.assertTrue(bt.all_kinds())
        self.assertEqual(bt.profession_of_kind("forge"), "smith")
        self.assertEqual(bt.profession_of_kind("farmhouse"), "farmer")
        self.assertEqual(bt.profession_of_kind("lodge"), "hunter")
        self.assertEqual(bt.profession_of_kind("mine"), "miner")
        self.assertIsNone(bt.profession_of_kind("shop"))     # a service bldg
        self.assertIsNone(bt.profession_of_kind("nonsense"))

    def test_is_workshop(self):
        self.assertTrue(bt.is_workshop("forge"))
        self.assertFalse(bt.is_workshop("temple"))

    def test_every_profession_is_a_real_producer(self):
        from engine.production import PROFESSIONS
        for kind, spec in bt.TYPES.items():
            prof = spec.get("profession")
            if prof is not None:
                self.assertIn(prof, PROFESSIONS, f"{kind}: bad profession")
            self.assertIn("function", spec)

    def test_specializations_reference_real_kinds(self):
        for name, kinds in bt.all_specializations().items():
            for k in kinds:
                self.assertIn(k, bt.TYPES, f"{name}: unknown kind {k}")


class TestRoomClassification(unittest.TestCase):
    def test_an_anvil_room_is_a_smithy(self):
        inter = Interior(name="X",
                         furniture=[{"name": "Anvil", "x": 1, "y": 1}])
        kind = bt.classify_interior(inter)
        self.assertEqual(bt.function_of_kind(kind), "smithy")
        self.assertEqual(bt.profession_of_kind(kind), "smith")

    def test_an_altar_room_is_a_temple(self):
        inter = Interior(name="Y",
                         furniture=[{"name": "Altar", "x": 1, "y": 1}])
        self.assertEqual(bt.function_of_kind(bt.classify_interior(inter)),
                         "temple")

    def test_a_plain_room_is_unclassified(self):
        inter = Interior(name="Z",
                         furniture=[{"name": "Table", "x": 1, "y": 1}])
        self.assertIsNone(bt.classify_interior(inter))


class TestOccupationFollowsBuilding(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.ps = self.engine.production

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _fake(self, home):
        class _N:
            pass
        n = _N()
        n.home_location = home
        return n

    def test_building_sets_the_trade(self):
        self.assertEqual(self.ps._building_profession(
            self._fake("Old Farmhouse")), "farmer")
        self.assertEqual(self.ps._building_profession(
            self._fake("Durgan's Forge")), "smith")
        self.assertEqual(self.ps._building_profession(
            self._fake("Hunter's Lodge")), "hunter")

    def test_no_home_no_building_trade(self):
        self.assertIsNone(self.ps._building_profession(self._fake("")))

    def test_a_farmhouse_villager_is_a_farmer_not_a_woodcutter(self):
        # occupation follows the building over the character class: a real
        # farmhouse resident (a villager by class) must come out a farmer.
        res = [n for n in self.engine.npc_manager.npcs.values()
               if "farmhouse" in getattr(n, "home_location", "").lower()]
        if not res:
            self.skipTest("no farmhouse resident spawned")
        self.assertEqual(self.ps._building_profession(res[0]), "farmer")


if __name__ == "__main__":
    unittest.main()
