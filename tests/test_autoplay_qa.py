"""Autoplay QA fixes (George, watching autoplay): the away-hero should
PICK UP items around it instead of strolling past, and characters should
FACE each other when they interact (talk / trade / fight)."""

import unittest

from engine.game_engine import GameEngine
from engine.agent_controller import drive_agents
from items.item_registry import create_item


class TestFacing(unittest.TestCase):
    def setUp(self):
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.p = self.e.player
        self.npc = next(iter(self.e.npc_manager.npcs.values()))

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def _place_npc(self, dx, dy):
        px, py = self.p.position
        self.npc.position = (px + dx, py + dy)

    def test_dialog_faces_both(self):
        self._place_npc(1, 0)                 # NPC to the east
        self.e.dialog_system.player_to_npc(self.npc.id)
        self.assertEqual(self.p.metadata.get("_face"), (1, 0))
        self.assertEqual(self.npc.metadata.get("_face"), (-1, 0))

    def test_combat_faces_both(self):
        self._place_npc(0, -1)                # NPC to the north
        # attacker and defender both turn to face each other
        self.e.combat_system.player_attack(self.npc.name)
        self.assertEqual(self.p.metadata.get("_face"), (0, -1))
        self.assertEqual(self.npc.metadata.get("_face"), (0, 1))

    def test_trade_faces_both(self):
        from engine import agent_trade
        self._place_npc(-1, 0)                 # merchant to the west
        # do_trade faces even if no deal is struck
        agent_trade.do_trade(self.e, self.p, self.npc)
        self.assertEqual(self.p.metadata.get("_face"), (-1, 0))
        self.assertEqual(self.npc.metadata.get("_face"), (1, 0))


class TestPickup(unittest.TestCase):
    def test_away_hero_grabs_nearby_loot(self):
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        p = e.player
        px, py = p.position

        def near():
            return sum(len(e.world.get_items_at(px + dx, py + dy))
                       for dx in range(-2, 3) for dy in range(-2, 3))

        base = near()
        for (dx, dy, iid) in [(1, 0, "potion"), (0, 1, "sword"),
                              (2, 0, "bread")]:
            e.world.add_item_to_ground(create_item(iid), px + dx, py + dy)
        self.assertEqual(near(), base + 3)
        e.roster.set_away(p, True)
        for _ in range(12):
            drive_agents(e)
            e.advance_turn()
        # the hero should have collected most of the loot around it
        self.assertLessEqual(near(), base + 1)
        e.end_game()

    def test_direct_pickup_works(self):
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        p = e.player
        e.world.add_item_to_ground(create_item("sword"), *p.position)
        msg = e.pickup_item()
        self.assertIn("pick up", msg.lower())
        e.end_game()


if __name__ == "__main__":
    unittest.main()
