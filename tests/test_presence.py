"""Interior presence tests (P9A.7) — same entities, both maps."""

import unittest

from engine.game_engine import GameEngine
from engine.presence import (building_containing, is_indoors,
                             assign_visitors, zone_position,
                             npc_adjacent_to_player)


class TestPresence(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.engine.world.time = 12 * 60

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _tavern_loc(self):
        return next(l for l in self.engine.world.locations
                    if "tavern" in l.name.lower()
                    and l.name in self.engine.interiors)

    def _put_npc_inside(self, loc):
        npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
        wmap = self.engine.world.map
        wmap.remove_character(npc)
        npc.position = (loc.x, loc.y)
        wmap.place_character(npc, loc.x, loc.y)
        return npc

    def test_footprint_position_is_indoors(self):
        loc = self._tavern_loc()
        npc = self._put_npc_inside(loc)
        self.assertEqual(is_indoors(self.engine, npc), loc.name)
        self.assertIsNone(is_indoors(self.engine, self.player))

    def test_indoors_npc_unreachable_from_the_street(self):
        loc = self._tavern_loc()
        npc = self._put_npc_inside(loc)
        wmap = self.engine.world.map
        wmap.remove_character(self.player)
        self.player.position = (loc.x - 1, loc.y)
        wmap.place_character(self.player, *self.player.position)
        self.assertFalse(
            npc_adjacent_to_player(self.engine, npc),
            "no talking through walls")

    def test_entering_assigns_visitors(self):
        loc = self._tavern_loc()
        npc = self._put_npc_inside(loc)
        inter = self.engine.interiors[loc.name]
        self.engine.door_manager.door(loc.name)["state"] = "open"
        wmap = self.engine.world.map
        wmap.remove_character(self.player)
        self.player.position = (loc.x + loc.width // 2,
                                loc.y + loc.height - 1)
        wmap.place_character(self.player, *self.player.position)
        self.engine.enter_building(loc)
        self.assertIn(npc.id, inter.visitors)
        zx, zy = inter.visitors[npc.id]
        self.assertTrue(0 < zx < inter.width - 1)
        self.assertTrue(0 < zy < inter.height - 1)

    def test_visitor_is_the_same_entity_and_talkable(self):
        loc = self._tavern_loc()
        npc = self._put_npc_inside(loc)
        inter = self.engine.interiors[loc.name]
        self.engine.current_interior = inter
        assign_visitors(self.engine, inter, loc.name)
        spot = zone_position(self.engine, npc)
        self.assertIsNotNone(spot)
        self.player.position = (spot[0] + 1, spot[1])
        self.assertTrue(
            npc_adjacent_to_player(self.engine, npc),
            "visitor beside the player must be interactable")
        # the SAME object: relationship changes stick
        npc.relationships[self.player.id] = 42
        self.assertEqual(
            self.engine.npc_manager.get_npc(npc.id)
            .relationships[self.player.id], 42)

    def test_assignment_is_deterministic(self):
        loc = self._tavern_loc()
        npc = self._put_npc_inside(loc)
        inter = self.engine.interiors[loc.name]
        first = dict(assign_visitors(self.engine, inter, loc.name))
        second = dict(assign_visitors(self.engine, inter, loc.name))
        self.assertEqual(first, second)

    def test_outdoor_npc_not_a_visitor(self):
        loc = self._tavern_loc()
        npc = self.engine.npc_manager.get_npc("guard_01")
        wmap = self.engine.world.map
        wmap.remove_character(npc)
        npc.position = (loc.x - 3, loc.y)
        wmap.place_character(npc, *npc.position)
        inter = self.engine.interiors[loc.name]
        assign_visitors(self.engine, inter, loc.name)
        self.assertNotIn(npc.id, inter.visitors)

    def test_melee_reaches_a_visitor(self):
        loc = self._tavern_loc()
        npc = self._put_npc_inside(loc)
        npc.hp = npc.max_hp = 99
        inter = self.engine.interiors[loc.name]
        self.engine.current_interior = inter
        assign_visitors(self.engine, inter, loc.name)
        spot = zone_position(self.engine, npc)
        self.player.position = (spot[0] + 1, spot[1])
        msg = self.engine.combat_system.player_attack(npc.name)
        self.assertNotIn("too far away", msg)

    def test_street_melee_cannot_reach_indoors(self):
        loc = self._tavern_loc()
        npc = self._put_npc_inside(loc)
        wmap = self.engine.world.map
        wmap.remove_character(self.player)
        self.player.position = (loc.x - 1, loc.y)
        wmap.place_character(self.player, *self.player.position)
        msg = self.engine.combat_system.player_attack(npc.name)
        self.assertIn("too far away", msg)


if __name__ == "__main__":
    unittest.main()
