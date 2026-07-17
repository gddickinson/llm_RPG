"""Tests for schedule-driven NPC movement (location keyword resolution)."""

import unittest

from engine.game_engine import GameEngine


class TestActionRouterLocations(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_resolve_tavern_keyword(self):
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        pos = self.engine.action_router._resolve_location_target(
            goren, "tavern")
        self.assertIsNotNone(pos)

    def test_resolve_forge_keyword(self):
        durgan = self.engine.npc_manager.get_npc("blacksmith_01")
        pos = self.engine.action_router._resolve_location_target(
            durgan, "forge")
        self.assertIsNotNone(pos)

    def test_resolve_home_keyword(self):
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        goren.home_location = "Oakvale Tavern"
        pos = self.engine.action_router._resolve_location_target(
            goren, "home")
        self.assertIsNotNone(pos)

    def test_resolve_unknown_keyword(self):
        npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
        pos = self.engine.action_router._resolve_location_target(
            npc, "nowhere in particular")
        self.assertIsNone(pos)

    def test_npc_moves_toward_target_keyword(self):
        # Move guard far from tavern, then issue "move tavern" — he should
        # step closer.
        guard = self.engine.npc_manager.get_npc("guard_01")
        self.engine.world.map.remove_character(guard)
        guard.position = (40, 35)
        self.engine.world.map.place_character(guard, *guard.position)

        # Tavern center should be in the village area
        for loc in self.engine.world.locations:
            if "Tavern" in loc.name:
                tavern_pos = loc.center()
                break
        else:
            self.skipTest("No tavern found")

        before_dist = ((guard.position[0] - tavern_pos[0]) ** 2 +
                       (guard.position[1] - tavern_pos[1]) ** 2) ** 0.5
        self.engine.action_router.process(
            guard, {"action": "move", "target": "tavern",
                    "dialog": "", "thoughts": "", "emotion": "",
                    "goal_update": ""})
        after_dist = ((guard.position[0] - tavern_pos[0]) ** 2 +
                      (guard.position[1] - tavern_pos[1]) ** 2) ** 0.5
        self.assertLess(after_dist, before_dist)

    def test_arrived_npc_mills_about_instead_of_freezing(self):
        # George: an NPC that reaches its scheduled location used to freeze on one
        # tile. Now it AMBLES within LOITER_RADIUS so idle towns keep moving.
        import random
        from engine.action_router import LOITER_RADIUS
        random.seed(3)
        loc = next((l for l in self.engine.world.locations
                    if "village" in l.name.lower()), None)
        if loc is None:
            self.skipTest("no village")
        center = loc.center()
        npc = next(iter(self.engine.npc_manager.npcs.values()))
        self.engine.world.map.remove_character(npc)
        npc.position = center
        self.engine.world.map.place_character(npc, *center)
        moves, seen = 0, set()
        for _ in range(80):
            before = npc.position
            self.engine.action_router.process(
                npc, {"action": "move", "target": loc.name})
            seen.add(npc.position)
            if npc.position != before:
                moves += 1
        self.assertGreater(moves, 15, "an arrived NPC ambles, it does not freeze")
        maxd = max(((p[0] - center[0]) ** 2 + (p[1] - center[1]) ** 2) ** 0.5
                   for p in seen)
        self.assertLessEqual(maxd, LOITER_RADIUS + 0.01, "stays near its spot")

    def test_direction_move_is_not_loitered(self):
        # a plain compass move still steps that way (loiter is location-only)
        guard = self.engine.npc_manager.get_npc("guard_01")
        self.engine.world.map.remove_character(guard)
        guard.position = (40, 35)
        self.engine.world.map.place_character(guard, *guard.position)
        before = guard.position
        self.engine.action_router.process(
            guard, {"action": "move", "target": "north"})
        self.assertEqual(guard.position, (before[0], before[1] - 1))


if __name__ == "__main__":
    unittest.main()
