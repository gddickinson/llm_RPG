"""A seeded GameEngine builds the same world every time: in one process,
and in a fresh process with a different string-hash seed."""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SNAP = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
from engine.game_engine import GameEngine
e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
               world_kind="combined", seed=int(sys.argv[1]))
e.start_game()
m = e.world.map
print(json.dumps({
    "terrain": "".join(t.value[0] for row in m.terrain for t in row),
    "places": [[l.name, l.x, l.y, l.width, l.height] for l in e.world.locations],
    "people": sorted([n.name, list(n.position)] for n in e.npc_manager.npcs.values()),
    "spawn": list(e.player.position)}))
"""


def snapshot(seed, hashseed):
    env = dict(os.environ, PYTHONHASHSEED=str(hashseed))
    out = subprocess.run([sys.executable, "-c", _SNAP, str(seed)], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


class TestWorldSeed(unittest.TestCase):
    def test_same_seed_same_world_across_processes(self):
        a = snapshot(11, 1)
        b = snapshot(11, 2)
        self.assertEqual(a["terrain"], b["terrain"])
        self.assertEqual(a["places"], b["places"])
        self.assertEqual(a["people"], b["people"])
        self.assertEqual(a["spawn"], b["spawn"])

    def test_same_seed_same_world_in_one_process(self):
        from engine.game_engine import GameEngine

        def build():
            e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                           world_kind="combined", seed=5)
            e.start_game()
            return ([(l.name, l.x, l.y) for l in e.world.locations],
                    sorted((n.name, tuple(n.position)) for n in e.npc_manager.npcs.values()))
        self.assertEqual(build(), build())

    def test_different_seeds_differ(self):
        self.assertNotEqual(snapshot(11, 1)["places"], snapshot(12, 1)["places"])


if __name__ == "__main__":
    unittest.main()
