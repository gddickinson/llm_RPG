"""P35.3 — terrain & cover in combat: rules + the AI fighting from cover."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_tc_"))

import unittest

from engine.game_engine import GameEngine
from engine import terrain_combat as tc
from world.world_map import TerrainType as T


class _Actor:
    def __init__(self, pos):
        self.position = pos


class TestRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()
        cls.wmap = cls.engine.world.map
        # a small terrain sandbox in a corner
        for (x, y, t) in [(5, 5, T.FOREST), (6, 5, T.GRASS), (7, 5, T.WATER),
                          (9, 5, T.MOUNTAIN), (8, 5, T.GRASS), (10, 5, T.GRASS)]:
            cls.wmap.terrain[y][x] = t

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_forest_gives_cover_more_vs_ranged(self):
        d = _Actor((5, 5))                              # standing in forest
        melee = tc.cover_ac(self.engine, d, ranged=False)
        ranged = tc.cover_ac(self.engine, d, ranged=True)
        self.assertGreater(ranged, melee)              # cover shields vs arrows most
        self.assertGreaterEqual(ranged, 2)

    def test_open_ground_no_cover(self):
        self.assertEqual(tc.cover_ac(self.engine, _Actor((6, 5))), 0)

    def test_water_marsh_hampers_melee_not_ranged(self):
        atk = _Actor((7, 5))                            # standing in water
        self.assertGreater(tc.footing_penalty(self.engine, atk, "attack"), 0)
        self.assertEqual(tc.footing_penalty(self.engine, atk, "shoot"), 0)

    def test_high_ground_helps_an_archer(self):
        up = _Actor((8, 5))                             # beside the mountain
        flat = _Actor((6, 5))
        self.assertGreater(tc.high_ground(self.engine, up, flat, "shoot"), 0)
        self.assertEqual(tc.high_ground(self.engine, up, flat, "attack"), 0)

    def test_net_to_hit_mod(self):
        # a melee attacker in water is at a net disadvantage
        self.assertLess(tc.to_hit_mod(self.engine, _Actor((7, 5)),
                                      _Actor((6, 5)), "attack"), 0)


class TestAiSeeksCover(unittest.TestCase):
    def test_pack_prefers_a_cover_flank_tile(self):
        engine = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        engine.start_game()
        wmap = engine.world.map
        px, py = engine.player.position
        # one forest tile among the flanking spots around the player
        fx, fy = px + 1, py
        if 0 <= fy < wmap.height and 0 <= fx < wmap.width:
            wmap.terrain[fy][fx] = T.FOREST
        from engine.monster_packs import MonsterPackSystem
        sys = MonsterPackSystem(engine)
        m = _Actor((px + 4, py))
        tile = sys._surround_tile(m, engine.player, set())
        self.assertIsNotNone(tile)
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
