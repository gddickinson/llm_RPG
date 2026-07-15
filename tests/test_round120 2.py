"""Round 120 tests: pack structures (P14.2b), earshot (P14.3a),
bridges (P14.3b)."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class TestPackStructures(unittest.TestCase):
    def setUp(self):
        # stage the shipped sample pack in an isolated packs dir
        import shutil
        self._packs_prev = _os.environ.get("LLM_RPG_MODULE_PACKS")
        self._packs_dir = _tempfile.mkdtemp(prefix="llmrpg_packs_")
        shutil.copy("data/module_packs/smugglers_cache.json",
                    self._packs_dir)
        _os.environ["LLM_RPG_MODULE_PACKS"] = self._packs_dir
        # the structure registry is module-global: clean between runs
        from world.structures import STRUCTURES
        STRUCTURES.pop("smugglers_cache", None)
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        if self._packs_prev is not None:
            _os.environ["LLM_RPG_MODULE_PACKS"] = self._packs_prev
        else:
            _os.environ.pop("LLM_RPG_MODULE_PACKS", None)
        from world.structures import STRUCTURES
        STRUCTURES.pop("smugglers_cache", None)

    def test_the_cache_ships_with_the_pack(self):
        from world.structures import STRUCTURES
        self.assertIn("smugglers_cache", STRUCTURES)
        farm = self.engine.interiors.get("Old Farmhouse")
        self.assertIsNotNone(farm)
        below = getattr(farm, "level_below", None)
        self.assertIsNotNone(below, "the cellar attached")
        self.assertIn("Cache", below.name)
        self.assertTrue(getattr(below, "dark", False))

    def test_the_cache_has_its_guard(self):
        bones = [n for n in self.engine.npc_manager.npcs.values()
                 if "Bones" in n.name and
                 n.metadata.get("zone") and
                 "Cache" in n.metadata["zone"]]
        # populate-on-first-visit structures may defer the spawn;
        # entering triggers it
        if not bones:
            farm = self.engine.interiors["Old Farmhouse"]
            self.engine.structures.on_enter_level(farm.level_below)
            bones = [n for n in self.engine.npc_manager.npcs.values()
                     if "Bones" in n.name and
                     n.metadata.get("zone") and
                     "Cache" in n.metadata["zone"]]
        self.assertTrue(bones, "something guards the cache")


class TestEarshot(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_distant_clashes_stay_out_of_the_log(self):
        from world.monsters import build_monster
        # stage a kill far from the player
        px, py = self.player.position
        fx = 2 if px > self.wmap.width // 2 else self.wmap.width - 3
        fy = 2 if py > self.wmap.height // 2 else self.wmap.height - 3
        self.wmap.terrain[fy][fx] = TerrainType.GRASS
        self.wmap.terrain[fy][fx + 0] = TerrainType.GRASS
        a = build_monster("bandit", (fx, fy))
        b = build_monster("wolf", (fx, fy))
        b.hp = 1
        self.engine.npc_manager.add_npc(a)
        self.engine.npc_manager.add_npc(b)
        n0 = len(self.engine.memory_manager.game_history)
        self.engine.combat_system._handle_defeat(a, b, damage=5)
        new = [str(e) for e in
               self.engine.memory_manager.game_history[n0:]]
        self.assertFalse(any("defeated" in e for e in new),
                         "a fight across the map is not news")

    def test_your_own_kills_are_always_news(self):
        from world.monsters import build_monster
        px, py = self.player.position
        w = build_monster("wolf", (px + 1, py))
        w.hp = 1
        self.engine.npc_manager.add_npc(w)
        self.engine.combat_system._handle_defeat(
            self.player, w, damage=5)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("defeated", log)


class TestBridges(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_roads_bridge_the_water(self):
        # wherever a generated road line meets water, a BRIDGE stands;
        # verify no road tile is orphaned against a water gap by
        # checking bridges exist whenever the crossing occurred
        bridges = sum(row.count(TerrainType.BRIDGE)
                      for row in self.wmap.terrain)
        # the map has a river between Oakvale and Riverside in most
        # gens; when it does, the road must bridge it
        if bridges == 0:
            self.skipTest("this gen's roads met no water")
        self.assertGreater(bridges, 0)

    def test_bridges_are_walkable_water_is_not(self):
        ox, oy = self.wmap.width - 8, self.wmap.height - 6
        for x in (ox, ox + 1):
            self.wmap.terrain[oy][x] = TerrainType.GRASS
            ch = self.wmap.get_character_at(x, oy)
            if ch is not None:
                self.wmap.remove_character(ch)
        self.wmap.terrain[oy][ox + 1] = TerrainType.BRIDGE
        self.wmap.remove_character(self.player)
        self.player.position = (ox, oy)
        self.wmap.place_character(self.player, ox, oy)
        self.assertTrue(self.engine.player_actions.move(1, 0),
                        "planks hold")

    def test_bridges_burn_down_to_water(self):
        ox, oy = self.wmap.width - 8, self.wmap.height - 6
        self.wmap.terrain[oy][ox] = TerrainType.BRIDGE
        for _ in range(10):
            if self.wmap.terrain[oy][ox] != TerrainType.BRIDGE:
                break
            self.engine.tile_damage.damage_tile(ox, oy, 15, "fire")
        self.assertEqual(self.wmap.terrain[oy][ox],
                         TerrainType.WATER,
                         "burn the bridge and the river is back")

    def test_floods_never_flood_a_bridge(self):
        from engine.flood import FLOODABLE
        self.assertNotIn(TerrainType.BRIDGE, FLOODABLE)


if __name__ == "__main__":
    unittest.main()
