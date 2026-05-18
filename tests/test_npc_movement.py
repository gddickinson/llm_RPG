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


if __name__ == "__main__":
    unittest.main()
