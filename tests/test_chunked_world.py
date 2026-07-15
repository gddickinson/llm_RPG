"""Tests for chunked-world streaming."""

import unittest

from engine.game_engine import GameEngine
from world.chunked_world import ChunkedWorld, WorldStreamer


class TestChunkedPlan(unittest.TestCase):
    def test_region_plan_deterministic(self):
        cw = ChunkedWorld(world_seed=42)
        a = cw.plan_for(1, 0)
        b = cw.plan_for(1, 0)
        self.assertEqual(a.seed, b.seed)

    def test_home_region_flavor(self):
        cw = ChunkedWorld(world_seed=42)
        self.assertEqual(cw.plan_for(0, 0).flavor, "home")

    def test_adjacent_regions_have_different_seeds(self):
        cw = ChunkedWorld(world_seed=42)
        s1 = cw.plan_for(1, 0).seed
        s2 = cw.plan_for(2, 0).seed
        self.assertNotEqual(s1, s2)


class TestWorldStreamer(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_streamer_initialized(self):
        self.assertIsNotNone(self.engine.world_streamer)
        self.assertEqual(self.engine.world_streamer.cw.current_region,
                         (0, 0))

    def test_at_world_edge(self):
        wmap = self.engine.world.map
        # Move player to east edge
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (wmap.width - 1, 5)
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        self.assertEqual(self.engine.world_streamer.at_world_edge(),
                         "east")

    def test_transit_moves_player_and_region(self):
        # Place at east edge then walk east
        wmap = self.engine.world.map
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (wmap.width - 1, 10)
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        ok = self.engine.move_player(1, 0)
        self.assertTrue(ok)
        self.assertEqual(self.engine.world_streamer.cw.current_region,
                         (1, 0))
        # Player on west edge of new region
        self.assertEqual(self.engine.player.position[0], 1)

    def test_round_trip_restores_locations(self):
        # Initial home has many locations
        original = list(self.engine.world.locations)
        self.assertGreater(len(original), 0)

        wmap = self.engine.world.map
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (wmap.width - 1, 10)
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        self.engine.move_player(1, 0)
        # Walk back west
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (0, 10)
        self.engine.world.map.place_character(self.engine.player,
                                              *self.engine.player.position)
        self.engine.move_player(-1, 0)
        self.assertEqual(self.engine.world_streamer.cw.current_region,
                         (0, 0))
        # Should have the same locations as before
        self.assertEqual(len(self.engine.world.locations), len(original))

    def test_npcs_belong_to_their_region(self):
        # The home villagers must NOT reappear in the next region over.
        s = self.engine.world_streamer
        home = set(self.engine.npc_manager.npcs)
        self.assertTrue(home, "the home region has a cast")
        s.transit("east")
        new = set(self.engine.npc_manager.npcs)
        self.assertFalse(home & new,
                         "home NPCs bled into the new region")

    def test_round_trip_restores_the_cast(self):
        s = self.engine.world_streamer
        home = set(self.engine.npc_manager.npcs)
        s.transit("east")
        s.transit("west")               # back home
        self.assertEqual(s.cw.current_region, (0, 0))
        self.assertTrue(home <= set(self.engine.npc_manager.npcs),
                        "the home cast returns when we come back")

    def test_a_companion_travels_between_regions(self):
        s = self.engine.world_streamer
        comp = next(iter(self.engine.npc_manager.npcs))
        self.engine.companion_manager.party.append(comp)
        others = set(self.engine.npc_manager.npcs) - {comp}
        s.transit("east")
        present = set(self.engine.npc_manager.npcs)
        self.assertIn(comp, present, "the companion crosses with you")
        self.assertFalse(others & present, "but the region's cast stays")
        cached = {n.id for n in s.cw.cached_npcs.get((0, 0), [])}
        self.assertNotIn(comp, cached, "companion isn't stowed in the region")


if __name__ == "__main__":
    unittest.main()
