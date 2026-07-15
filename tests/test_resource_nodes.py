"""Depletable, regrowing resource nodes (P16.4): groves."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine                # noqa: E402
from world.resource_nodes import ResourceNodeSystem, SPECS  # noqa: E402
from world.world_map import TerrainType                  # noqa: E402
from items.item_registry import create_item              # noqa: E402


class TestResourceNodes(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.rn = self.engine.resource_nodes

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _a_grove(self):
        (x, y), node = next(iter(self.rn.nodes.items()))
        return x, y, node

    # ---- seeding ---------------------------------------------------

    def test_groves_are_seeded_on_forest(self):
        self.assertTrue(self.rn.nodes, "groves should seed at world start")
        wmap = self.engine.world.map
        for (x, y), node in self.rn.nodes.items():
            self.assertEqual(node["kind"], "grove")
            self.assertEqual(wmap.terrain[y][x], TerrainType.FOREST)

    def test_seed_is_idempotent(self):
        self.assertEqual(self.rn.seed(), 0)   # already seeded

    # ---- harvest / deplete -----------------------------------------

    def test_harvest_spends_a_charge(self):
        x, y, node = self._a_grove()
        before = node["charges"]
        self.assertTrue(self.rn.harvest(x, y, "woodcutting"))
        self.assertEqual(node["charges"], before - 1)

    def test_wrong_skill_spends_nothing(self):
        x, y, node = self._a_grove()
        before = node["charges"]
        self.assertFalse(self.rn.harvest(x, y, "mining"))
        self.assertEqual(node["charges"], before)

    def test_felling_turns_the_tile_to_grass(self):
        x, y, node = self._a_grove()
        for _ in range(node["max"]):
            self.rn.harvest(x, y, "woodcutting")
        self.assertEqual(node["charges"], 0)
        self.assertEqual(self.engine.world.map.terrain[y][x],
                         TerrainType.GRASS)
        self.assertIsNotNone(node["regrow_day"])

    def test_depleted_node_spends_nothing(self):
        x, y, node = self._a_grove()
        for _ in range(node["max"]):
            self.rn.harvest(x, y, "woodcutting")
        self.assertFalse(self.rn.harvest(x, y, "woodcutting"))

    # ---- regrowth --------------------------------------------------

    def test_regrows_only_after_its_rest(self):
        x, y, node = self._a_grove()
        for _ in range(node["max"]):
            self.rn.harvest(x, y, "woodcutting")
        regrow_day = node["regrow_day"]
        self.engine.world.time = (regrow_day - 1) * 24 * 60
        self.assertEqual(self.rn.run_day(), 0)
        self.assertEqual(self.engine.world.map.terrain[y][x],
                         TerrainType.GRASS)
        self.engine.world.time = regrow_day * 24 * 60
        self.assertGreaterEqual(self.rn.run_day(), 1)
        self.assertEqual(self.engine.world.map.terrain[y][x],
                         TerrainType.FOREST)
        self.assertEqual(node["charges"], node["max"])

    # ---- gathering integration -------------------------------------

    def test_chopping_a_grove_spends_its_charge(self):
        x, y, node = self._a_grove()
        self.engine.player.position = (x, y)
        self.engine.player.inventory.append(create_item("crude_axe"))
        before = node["charges"]
        self.engine.gathering_manager.gather()
        self.assertLess(node["charges"], before,
                        "woodcutting a grove spends a charge")

    # ---- persistence -----------------------------------------------

    def test_round_trip(self):
        x, y, node = self._a_grove()
        self.rn.harvest(x, y, "woodcutting")
        clone = ResourceNodeSystem(self.engine)
        clone.from_dict(self.rn.to_dict())
        self.assertEqual(clone.nodes, self.rn.nodes)

    def test_survives_save_load(self):
        x, y, node = self._a_grove()
        for _ in range(node["max"]):
            self.rn.harvest(x, y, "woodcutting")   # fell it
        before = {k: dict(v) for k, v in self.rn.nodes.items()}
        self.engine.save_game(name="p164_roundtrip")
        e2 = GameEngine(llm_provider="heuristic",
                        enable_npc_processes=False)
        e2.start_game()
        self.assertTrue(e2.load_game(name="p164_roundtrip"))
        self.assertEqual(e2.resource_nodes.nodes, before)
        e2.end_game()


if __name__ == "__main__":
    unittest.main()
