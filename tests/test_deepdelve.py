"""GX.5 The Oakvale Deepdelve — a deep, multi-mouth shared dungeon."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from world.dungeon import generate_multilevel


class TestDeepdelveDepth(unittest.TestCase):
    def test_generate_multilevel_forced_depth(self):
        # GX.5: an explicit depth forces exactly that many linked floors.
        d = generate_multilevel("The Deepdelve", seed=1, depth=6)
        n, cur = 1, d
        while cur.level_below is not None:
            cur = cur.level_below
            n += 1
        self.assertEqual(n, 6, "a deep delve runs the requested floors")
        # Stairs link both ways.
        self.assertIsNotNone(d.stairs_down)
        self.assertIsNotNone(d.level_below.stairs_up)

    def test_default_depth_still_shallow(self):
        d = generate_multilevel("Dark Cave", seed=2)
        n, cur = 1, d
        while cur.level_below is not None:
            cur = cur.level_below
            n += 1
        self.assertIn(n, (2, 3), "plain caves stay the classic 2-3")


class TestDeepdelveSystem(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.dd = self.engine.deepdelve

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_mouths_seeded(self):
        self.assertTrue(self.dd.is_active())
        self.assertGreaterEqual(len(self.dd.mouths), 1)

    def test_mouths_are_deep_cave_locations(self):
        wmap = self.engine.world.map
        for m in self.dd.mouths:
            x, y = m["pos"]
            self.assertEqual(wmap.terrain[y][x], TerrainType.CAVE,
                             f"{m['name']} is a cave mouth")
            loc = self.engine.world.get_location_at(x, y)
            self.assertIsNotNone(loc)
            self.assertEqual(loc.get_property("dungeon_key"), "deepdelve")
            self.assertTrue(loc.get_property("deep_dungeon"))
            self.assertGreaterEqual(loc.get_property("deep_levels", 0), 5)

    def test_mouths_are_spread_and_far_from_start(self):
        px, py = self.engine.player.position
        pts = [tuple(m["pos"]) for m in self.dd.mouths]
        for (x, y) in pts:
            self.assertGreaterEqual(abs(x - px) + abs(y - py), 12,
                                    "a mouth is out in the wilds")
        # No two mouths sit on top of each other.
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                (ax, ay), (bx, by) = pts[i], pts[j]
                self.assertGreater(abs(ax - bx) + abs(ay - by), 6,
                                   "mouths are spread around the region")

    def test_entering_yields_a_deep_dungeon(self):
        x, y = self.dd.mouths[0]["pos"]
        self.engine.player.position = (x, y)
        msg = self.engine.enter_dungeon()
        self.assertIn("Deepdelve", msg)
        d = self.engine.current_dungeon
        n, cur = 1, d
        while getattr(cur, "level_below", None) is not None:
            cur = cur.level_below
            n += 1
        self.assertGreaterEqual(n, 5, "the delve is genuinely deep")

    def test_all_mouths_share_one_dungeon(self):
        if len(self.dd.mouths) < 2:
            self.skipTest("need two mouths to prove sharing")
        # Enter from mouth 0.
        x0, y0 = self.dd.mouths[0]["pos"]
        self.engine.player.position = (x0, y0)
        self.engine.enter_dungeon()
        self.engine.exit_dungeon()
        # Enter from mouth 1 — still ONE cached dungeon under the shared key.
        x1, y1 = self.dd.mouths[1]["pos"]
        self.engine.player.position = (x1, y1)
        self.engine.enter_dungeon()
        self.assertIn("deepdelve", self.engine.dungeons)
        self.assertEqual(len(self.engine.dungeons), 1,
                         "every mouth opens the same shared dungeon")

    def test_return_to_entry_mouth(self):
        x, y = self.dd.mouths[0]["pos"]
        self.engine.player.position = (x, y)
        self.engine.enter_dungeon()
        self.assertEqual(tuple(self.engine.dungeon_return_pos), (x, y))
        self.engine.exit_dungeon()
        self.assertEqual(self.engine.player.position, (x, y),
                         "you surface at the mouth you descended by")

    def test_persistence_round_trip(self):
        self.dd.mouths.append({"name": "X", "pos": [3, 3], "key": "deepdelve",
                               "legend": "", "guards": []})
        data = self.dd.to_dict()
        fresh = GameEngine(llm_provider="heuristic",
                           enable_npc_processes=False)
        fresh.start_game()
        fresh.deepdelve.from_dict(data)
        self.assertEqual([m["name"] for m in fresh.deepdelve.mouths],
                         [m["name"] for m in self.dd.mouths])
        fresh.end_game()


class TestDeepdelveSecret(unittest.TestCase):
    """GX.5b — the SECRET Oakvale stair into the same Deepdelve."""

    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.dd = self.engine.deepdelve

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_secret_seeds_hidden_near_oakvale(self):
        s = self.dd.secret
        self.assertIsNotNone(s, "the hidden Oakvale stair is seeded")
        self.assertFalse(s["revealed"])
        sx, sy = s["pos"]
        # Not a cave yet — it reads as ordinary ground until searched.
        self.assertNotEqual(self.engine.world.map.terrain[sy][sx],
                            TerrainType.CAVE)
        loc = self.engine.world.get_location_at(sx, sy)
        self.assertTrue(loc.get_property("hidden"))
        self.assertEqual(loc.get_property("dungeon_key"), "deepdelve")
        self.assertFalse(loc.get_property("deepdelve_mouth"))
        # Tucked within the village.
        ov = next((l for l in self.engine.world.locations
                   if l.name == "Oakvale Village"), None)
        if ov:
            ocx, ocy = ov.center()
            self.assertLessEqual(abs(sx - ocx) + abs(sy - ocy), 10)

    def test_secret_near_only_when_adjacent_and_unrevealed(self):
        sx, sy = self.dd.secret["pos"]
        self.assertIsNotNone(self.dd.secret_near((sx, sy)))
        self.assertIsNotNone(self.dd.secret_near((sx + 1, sy)))
        self.assertIsNone(self.dd.secret_near((sx + 5, sy)))
        self.dd.reveal_secret()
        self.assertIsNone(self.dd.secret_near((sx, sy)),
                          "no longer 'near' once found")

    def test_reveal_stamps_a_descendable_cave(self):
        sx, sy = self.dd.secret["pos"]
        msg = self.dd.reveal_secret()
        self.assertTrue(msg)
        self.assertEqual(self.engine.world.map.terrain[sy][sx],
                         TerrainType.CAVE)
        loc = self.engine.world.get_location_at(sx, sy)
        self.assertTrue(loc.get_property("deepdelve_mouth"))
        self.assertFalse(loc.get_property("hidden"))
        # Idempotent — searching again does nothing.
        self.assertIsNone(self.dd.reveal_secret())

    def test_secret_opens_the_shared_deepdelve(self):
        sx, sy = self.dd.secret["pos"]
        self.dd.reveal_secret()
        self.engine.player.position = (sx, sy)
        msg = self.engine.enter_dungeon()
        self.assertIn("Deepdelve", msg)
        self.assertIn("deepdelve", self.engine.dungeons)
        # Deep — the same 6-floor complex the wilderness mouths open.
        n, cur = 1, self.engine.current_dungeon
        while getattr(cur, "level_below", None) is not None:
            cur = cur.level_below
            n += 1
        self.assertGreaterEqual(n, 5)

    def test_search_hint_then_descend_hint(self):
        from ui.hints import context_hints
        sx, sy = self.dd.secret["pos"]
        self.engine.player.position = (sx + 1, sy)
        self.assertTrue(any("search" in h.lower()
                            for h in context_hints(self.engine)),
                        "a cue to search the hollow ground")
        self.dd.reveal_secret()
        self.engine.player.position = (sx, sy)
        self.assertTrue(any("Deepdelve" in h
                            for h in context_hints(self.engine)),
                        "once found, a cue to descend")

    def test_secret_persists(self):
        self.dd.reveal_secret()
        data = self.dd.to_dict()
        fresh = GameEngine(llm_provider="heuristic",
                           enable_npc_processes=False)
        fresh.start_game()
        fresh.deepdelve.from_dict(data)
        self.assertIsNotNone(fresh.deepdelve.secret)
        self.assertTrue(fresh.deepdelve.secret["revealed"])
        fresh.end_game()


if __name__ == "__main__":
    unittest.main()
