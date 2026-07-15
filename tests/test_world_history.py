"""P36.3 — deep-history world sim: foundings, wars, ruins, chronicle + Y-journal."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_wh_"))

import unittest

from world import world_history as wh
from world.world_map import TerrainType as T


def _terrain(w, h):
    # mostly land with a lake band, so score_site has water nearby
    grid = [[T.GRASS for _ in range(w)] for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if (x + y) % 11 == 0:
                grid[y][x] = T.FOREST
            if h // 3 <= y <= h // 3 + 1:
                grid[y][x] = T.WATER
    return grid


class TestSimulate(unittest.TestCase):
    def test_produces_foundings_wars_ruins(self):
        r = wh.simulate(_terrain(60, 40), seed=7)
        self.assertTrue(r["settlements"])
        self.assertTrue(r["ruins"])
        self.assertTrue(r["chronicle"])
        joined = " ".join(r["chronicle"]).lower()
        self.assertIn("founded", joined)
        self.assertIn("razed", joined)

    def test_ruins_have_place_and_legend(self):
        r = wh.simulate(_terrain(60, 40), seed=3)
        for ru in r["ruins"]:
            self.assertIsInstance(ru.x, int)
            self.assertIsInstance(ru.y, int)
            self.assertTrue(ru.legend)
            self.assertGreater(ru.year, 0)

    def test_seed_reproducible(self):
        a = wh.simulate(_terrain(60, 40), seed=9)["chronicle"]
        b = wh.simulate(_terrain(60, 40), seed=9)["chronicle"]
        c = wh.simulate(_terrain(60, 40), seed=10)["chronicle"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class TestChronicleJournal(unittest.TestCase):
    def test_seed_pregame_shows_in_the_journal(self):
        from engine.chronicle import Chronicle

        class _W:
            time = 0

        class _Eng:
            world = _W()
        c = Chronicle(_Eng())
        c.seed_pregame(["Year 87: the Hill clans founded Karrathal.",
                        "Year 726: war razed Karrathal — now ruins."])
        text = "\n".join(c.lines())
        self.assertIn("Chronicle of the Ages", text)
        self.assertIn("Karrathal", text)

    def test_pregame_round_trips(self):
        from engine.chronicle import Chronicle

        class _W:
            time = 0

        class _Eng:
            world = _W()
        c = Chronicle(_Eng())
        c.seed_pregame(["Year 1: a founding."])
        d = c.to_dict()
        c2 = Chronicle(_Eng())
        c2.from_dict(d)
        self.assertEqual(c2.pregame, ["Year 1: a founding."])


if __name__ == "__main__":
    unittest.main()
