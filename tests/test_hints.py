"""Tests for contextual key hints (P0.7 — discoverability)."""

import unittest

from engine.game_engine import GameEngine
from ui.hints import context_hints, MAX_HINTS
from world.world_map import TerrainType


class TestContextHints(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _isolate_player(self, pos=(2, 2)):
        """Move player somewhere empty so no NPC hints interfere."""
        self.player.position = pos
        for npc in self.engine.npc_manager.npcs.values():
            px, py = npc.position
            if abs(px - pos[0]) <= 2 and abs(py - pos[1]) <= 2:
                npc.position = (60, 60)

    def test_cap_and_no_duplicates(self):
        hints = context_hints(self.engine)
        self.assertLessEqual(len(hints), MAX_HINTS)
        self.assertEqual(len(hints), len(set(hints)))

    def test_talk_hint_near_friendly_npc(self):
        self._isolate_player()
        npc = next(n for n in self.engine.npc_manager.npcs.values()
                   if n.is_active() and getattr(
                       n.character_class, "value", "") not in
                   ("brigand", "troll", "monster"))
        npc.position = (3, 2)
        hints = context_hints(self.engine)
        self.assertTrue(any("[T] talk to" in h for h in hints), hints)

    def test_attack_hint_near_enemy(self):
        self._isolate_player()
        hostile = next((n for n in self.engine.npc_manager.npcs.values()
                        if n.is_active() and getattr(
                            n.character_class, "value", "") in
                        ("brigand", "troll", "monster")), None)
        if hostile is None:
            self.skipTest("no hostile NPC in demo world")
        hostile.position = (3, 2)
        hints = context_hints(self.engine)
        self.assertTrue(any("[F] attack" in h for h in hints), hints)

    def test_pickup_hint_on_ground_item(self):
        self._isolate_player()
        from items.item_registry import create_item
        item = create_item("potion")
        self.engine.world.add_item_to_ground(item, 2, 2)
        hints = context_hints(self.engine)
        self.assertTrue(any("[G] pick up" in h for h in hints), hints)

    def test_forage_hint_on_forest(self):
        wmap = self.engine.world.map
        spot = None
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.get_terrain_at(x, y) == TerrainType.FOREST:
                    spot = (x, y)
                    break
            if spot:
                break
        if spot is None:
            self.skipTest("no forest tile")
        self._isolate_player(spot)
        hints = context_hints(self.engine)
        self.assertTrue(any("[Z] forage" in h for h in hints), hints)

    def test_leave_hint_inside_interior(self):
        if not self.engine.interiors:
            self.skipTest("no interiors")
        self.engine.current_interior = next(
            iter(self.engine.interiors.values()))
        hints = context_hints(self.engine)
        self.assertIn("[TAB] leave the building", hints)
        self.engine.current_interior = None

    def test_recruit_hint_for_trusted_adjacent_npc(self):
        self._isolate_player()
        npc = next((n for n in self.engine.npc_manager.npcs.values()
                    if n.is_active() and getattr(
                        n.character_class, "value", "") in
                    ("warrior", "bard", "cleric", "wizard", "ranger",
                     "paladin")), None)
        if npc is None:
            self.skipTest("no recruitable NPC")
        npc.position = (3, 2)
        npc.modify_relationship(self.player.id, 50)
        hints = context_hints(self.engine)
        self.assertTrue(any("[P] invite" in h for h in hints), hints)


if __name__ == "__main__":
    unittest.main()
