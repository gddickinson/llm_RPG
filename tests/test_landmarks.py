"""Landmarks off-origin (P21.5).

Streamed regions used to be procedural noise. Now each one past the home
region seeds named landmarks — a ruin, a shrine, a dark hollow that leads
underground — deterministically, so the wider world has real places."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lmk_"))

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


def _landmarks(engine):
    return [l for l in engine.world.locations if l.get_property("landmark")]


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.ws = self.engine.world_streamer

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestLandmarks(_Base):
    def test_the_home_region_has_no_seeded_landmarks(self):
        self.assertEqual(_landmarks(self.engine), [],
                         "the authored home region isn't landmark-seeded")

    def test_a_streamed_region_gets_named_landmarks(self):
        self.ws.transit("east")
        lms = _landmarks(self.engine)
        self.assertTrue(lms, "off-origin regions aren't empty noise")
        self.assertTrue(all(l.name for l in lms))

    def test_landmarks_are_deterministic_per_region(self):
        self.ws.transit("east")
        a = sorted((l.name, l.x, l.y) for l in _landmarks(self.engine))
        self.ws.transit("west")            # home
        self.ws.transit("east")            # same region again
        b = sorted((l.name, l.x, l.y) for l in _landmarks(self.engine))
        self.assertEqual(a, b, "the same region always holds the same places")

    def test_cave_landmarks_are_real_dungeon_entrances(self):
        # over a sweep of regions, a cave-mouth landmark stamps a CAVE tile
        found_cave = False
        for i in range(1, 16):
            self.engine.world_streamer._seed_landmarks(i, 0, seed=1000 + i)
            for l in _landmarks(self.engine):
                if self.engine.world.map.terrain[l.y][l.x] == TerrainType.CAVE:
                    found_cave = True
            if found_cave:
                break
            self.engine.world.locations = []   # clear for the next sweep
        self.assertTrue(found_cave,
                        "some landmark is a cave that leads underground")


if __name__ == "__main__":
    unittest.main()
