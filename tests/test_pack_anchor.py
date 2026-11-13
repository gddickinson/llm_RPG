"""Module-pack structures tolerate a world without their named anchor
(engine/pack_anchor): the sample smugglers_cache pack, anchored to
"Old Farmhouse", now loads on the combined world."""

import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSmugglersCacheOnCombined(unittest.TestCase):
    def setUp(self):
        from tests import clean_dm_library
        clean_dm_library()
        from world.structures import STRUCTURES
        STRUCTURES.pop("smugglers_cache", None)
        self._packs = os.environ.get("LLM_RPG_MODULE_PACKS")
        os.environ["LLM_RPG_MODULE_PACKS"] = os.path.join(ROOT, "data", "module_packs")
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                                 world_kind="combined", seed=4)
        self.engine.start_game()

    def tearDown(self):
        os.environ["LLM_RPG_MODULE_PACKS"] = self._packs or ""
        from tests import clean_dm_library
        clean_dm_library()
        from world.structures import STRUCTURES
        STRUCTURES.pop("smugglers_cache", None)
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_cache_attaches_to_a_farmhouse(self):
        from world.structures import STRUCTURES
        self.assertIn("smugglers_cache", STRUCTURES)
        anchor = STRUCTURES["smugglers_cache"]["attach_to"]
        self.assertIn("farmhouse", anchor.lower())
        inter = self.engine.interiors.get(anchor)
        self.assertIsNotNone(inter, anchor)
        self.assertEqual(getattr(inter, "structure_id", None), "smugglers_cache")

    def test_known_cache_reanchors_in_a_classic_world(self):
        """The Legendarium remembers the cache with its combined-world anchor;
        a classic world must still attach it (to its own Old Farmhouse)."""
        from tests import clean_dm_library
        from engine.game_engine import GameEngine
        from world.structures import STRUCTURES
        self.assertIn("Oakvale Farmhouse", STRUCTURES["smugglers_cache"]["attach_to"])
        classic = GameEngine(llm_provider="heuristic", enable_npc_processes=False, seed=4)
        classic.start_game()
        try:
            farm = classic.interiors.get("Old Farmhouse")
            self.assertIsNotNone(farm)
            self.assertEqual(getattr(farm, "structure_id", None), "smugglers_cache")
        finally:
            classic.end_game()
            clean_dm_library()


class TestResolveAnchor(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic", enable_npc_processes=False, seed=8)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_exact_name_kept(self):
        from engine.pack_anchor import resolve_anchor
        name = self.engine.world.locations[0].name
        self.assertEqual(resolve_anchor(self.engine, name), name)

    def test_unknown_kind_plants_a_building(self):
        from engine.pack_anchor import resolve_anchor
        from world.world_map import TerrainType
        name = resolve_anchor(self.engine, "Hermit's Bothy")
        self.assertEqual(name, "Hermit's Bothy")
        loc = next(l for l in self.engine.world.locations if l.name == name)
        self.assertEqual(self.engine.world.map.terrain[loc.y][loc.x], TerrainType.BUILDING)
        self.assertEqual(loc.properties.get("kind"), "bothy")


if __name__ == "__main__":
    unittest.main()
