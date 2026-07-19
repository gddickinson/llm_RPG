"""Boxed-in fixes (George): swap past friendlies, consistent
indoor blocking."""

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType


class TestSqueezePast(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 10, self.wmap.height - 8
        for y in range(self.oy - 1, self.oy + 4):
            for x in range(self.ox - 1, self.ox + 5):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, *self.player.position)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put_npc(self, npc, x, y):
        self.wmap.remove_character(npc)
        npc.position = (x, y)
        self.wmap.place_character(npc, x, y)
        return npc

    def test_bumping_a_friendly_swaps_places(self):
        npc = next(n for n in self.engine.npc_manager.npcs.values()
                   if getattr(n.character_class, "value", "") in
                   ("merchant", "villager") and n.is_active())
        self._put_npc(npc, self.ox + 1, self.oy)
        n_before = len(self.engine.memory_manager.game_history)
        moved = self.engine.player_actions.move(1, 0)
        self.assertTrue(moved, "friendlies must let you squeeze past")
        self.assertEqual(self.player.position, (self.ox + 1, self.oy))
        self.assertEqual(npc.position, (self.ox, self.oy))
        # scan every beat this move produced — an ambient encounter/weather
        # beat can crowd a small tail window (the documented pattern)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[n_before:])
        self.assertIn("squeeze past", log)

    def test_hostiles_hold_the_line(self):
        wolf = build_monster("wolf", (self.ox + 1, self.oy))
        wolf.hp = wolf.max_hp = 99
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        moved = self.engine.player_actions.move(1, 0)
        self.assertFalse(moved, "monsters must block")
        self.assertEqual(self.player.position, (self.ox, self.oy))

    def test_indoor_visitor_blocks_at_displayed_position(self):
        interior = next(i for n, i in self.engine.interiors.items()
                        if "tavern" in n.lower())
        self.engine.current_interior = interior
        npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
        spot = (2, 2)
        interior.visitors = {npc.id: spot}
        # standing beside the visitor, walking onto them swaps
        self.player.position = (spot[0] - 1, spot[1])
        moved = self.engine.player_actions.move(1, 0)
        self.assertTrue(moved)
        self.assertEqual(tuple(self.player.position), spot)
        self.assertEqual(tuple(interior.visitors[npc.id]),
                         (spot[0] - 1, spot[1]),
                         "the visitor takes your old tile")
        self.engine.current_interior = None

    def test_overworld_coords_never_block_indoors(self):
        from world.world_map import TerrainType
        interior = next(i for n, i in self.engine.interiors.items()
                        if "tavern" in n.lower())
        self.engine.current_interior = interior
        npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
        # find two horizontally-adjacent FLOOR tiles (the GX.3 bigger layout
        # moved the walls, so don't hardcode a tile)
        spot = next(
            ((x, y) for y in range(1, interior.height - 1)
             for x in range(1, interior.width - 2)
             if interior.terrain[y][x] != TerrainType.BUILDING
             and interior.terrain[y][x + 1] != TerrainType.BUILDING), None)
        self.assertIsNotNone(spot, "two adjacent floor tiles exist")
        px, py = spot
        # the NPC's OVERWORLD position happens to equal the destination zone
        # tile; without a visitor entry it must not block
        self.wmap.remove_character(npc)
        npc.position = (px + 1, py)
        interior.visitors = {}
        self.player.position = (px, py)
        moved = self.engine.player_actions.move(1, 0)
        self.assertTrue(moved,
                        "phantom overworld coordinates must not block")
        self.engine.current_interior = None


if __name__ == "__main__":
    unittest.main()
