"""Walls are solid (bug-fix 2026-07-12).

NPCs and monsters used to phase straight through building walls — on the
overworld (`move_character` never blocked BUILDING) and inside a zone
(zone-native monsters were stepped on the overworld grid, ignoring the
zone's own walls). The installed `wall_guard` closes both."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from world.monsters import build_monster


class TestWallGuard(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    # ---- helpers ---------------------------------------------------

    def _free(self, x, y):
        return ((x, y) not in self.wmap.characters
                and 0 <= x < self.wmap.width and 0 <= y < self.wmap.height)

    def _wall_with_open_west(self):
        """A BUILDING tile whose western neighbour is open, non-building."""
        for y in range(1, self.wmap.height - 1):
            for x in range(1, self.wmap.width - 1):
                if (self.wmap.terrain[y][x] == TerrainType.BUILDING
                        and self.wmap.terrain[y][x - 1] != TerrainType.BUILDING
                        and self._free(x, y) and self._free(x - 1, y)):
                    return x, y
        return None

    def _enterable(self):
        return next((l for l in self.engine.world.locations
                     if l.name in self.engine.interiors), None)

    # ---- overworld -------------------------------------------------

    def test_monster_cannot_enter_a_building_wall(self):
        spot = self._wall_with_open_west()
        self.assertIsNotNone(spot, "expected a building with an open side")
        bx, by = spot
        w = build_monster("wolf", (bx - 1, by))
        self.engine.npc_manager.add_npc(w)
        self.wmap.place_character(w, bx - 1, by)
        self.assertFalse(self.wmap.move_character(w, bx, by),
                         "a monster must not phase into a building wall")
        self.assertEqual(w.position, (bx - 1, by))

    def test_flier_also_cannot_phase_a_building(self):
        spot = self._wall_with_open_west()
        bx, by = spot
        wisp = build_monster("marsh_wisp", (bx - 1, by))
        self.assertTrue(wisp.metadata.get("behavior", {}).get("flying"))
        self.engine.npc_manager.add_npc(wisp)
        self.wmap.place_character(wisp, bx - 1, by)
        self.assertFalse(self.wmap.move_character(wisp, bx, by),
                         "a flier floats over water, not through walls")

    def test_open_ground_still_walkable(self):
        # somewhere with grass on both sides
        for y in range(1, self.wmap.height - 1):
            for x in range(2, self.wmap.width - 1):
                if (self.wmap.terrain[y][x] == TerrainType.GRASS
                        and self.wmap.terrain[y][x - 1] == TerrainType.GRASS
                        and self._free(x, y) and self._free(x - 1, y)):
                    w = build_monster("wolf", (x - 1, y))
                    self.engine.npc_manager.add_npc(w)
                    self.wmap.place_character(w, x - 1, y)
                    self.assertTrue(self.wmap.move_character(w, x, y),
                                    "the guard must not block open ground")
                    return
        self.skipTest("no open grass pair found")

    def test_the_door_admits_passage(self):
        loc = self._enterable()
        self.assertIsNotNone(loc)
        dx = loc.x + loc.width // 2
        dy = loc.y + loc.height - 1          # south door tile
        outside = (dx, dy + 1)               # tile just outside the door
        if not (self._free(*outside)
                and self.wmap.terrain[outside[1]][outside[0]]
                != TerrainType.BUILDING):
            self.skipTest("door approach not open in this layout")
        w = build_monster("wolf", outside)
        w.id = "wolf_door"
        self.engine.npc_manager.add_npc(w)
        self.wmap.place_character(w, *outside)
        self.assertTrue(self.wmap.move_character(w, dx, dy),
                        "the door tile is the one gap in the wall")

    def test_indoor_npc_cannot_leave_through_a_side_wall(self):
        # an NPC on a footprint's SIDE wall (not the door) may not step
        # onto the street through it — only the door tile admits passage
        spot = self._wall_with_open_west()
        self.assertIsNotNone(spot)
        bx, by = spot
        # confirm the open-west tile is not this building's door
        loc = self.engine.world.get_location_at(bx, by)
        door = None
        if loc is not None and loc.name in self.engine.interiors:
            door = (loc.x + loc.width // 2, loc.y + loc.height - 1)
        if (bx, by) == door:
            self.skipTest("the sampled wall tile is the door")
        n = build_monster("goblin", (bx, by))       # stand it on the wall
        n.id = "indoor_test"
        self.engine.npc_manager.add_npc(n)
        self.wmap.place_character(n, bx, by)
        self.assertFalse(self.wmap.move_character(n, bx - 1, by),
                         "no exit through a side wall")
        self.assertEqual(n.position, (bx, by))

    # ---- inside a zone ---------------------------------------------

    def test_zone_monster_cannot_phase_a_zone_wall(self):
        loc = self._enterable()
        self.engine.enter_building(loc)
        zone = self.engine.active_zone()
        self.assertIsNotNone(zone)
        target = None
        for y in range(zone.height):
            for x in range(zone.width):
                if zone.terrain[y][x] == TerrainType.BUILDING:
                    for ax, ay in ((x - 1, y), (x + 1, y),
                                   (x, y - 1), (x, y + 1)):
                        if (0 <= ax < zone.width and 0 <= ay < zone.height
                                and zone.terrain[ay][ax]
                                != TerrainType.BUILDING):
                            target = ((ax, ay), (x, y))
                            break
                if target:
                    break
            if target:
                break
        self.assertIsNotNone(target)
        (fx, fy), (wx, wy) = target
        m = build_monster("wolf", (fx, fy))
        m.id = "enc_zonewall"
        m.metadata["zone"] = zone.name
        self.engine.npc_manager.add_npc(m)
        self.assertFalse(self.wmap.move_character(m, wx, wy),
                         "a zone monster must not phase a zone wall")
        self.assertEqual(m.position, (fx, fy))

    def test_zone_floor_still_walkable(self):
        loc = self._enterable()
        self.engine.enter_building(loc)
        zone = self.engine.active_zone()
        # two adjacent floor tiles
        for y in range(zone.height):
            for x in range(1, zone.width):
                # the move routes through the OVERWORLD wmap, so the zone-local
                # destination coords must be free there too (else a same-coord
                # overworld entity blocks it — a cross-space phantom)
                if (zone.terrain[y][x] != TerrainType.BUILDING
                        and zone.terrain[y][x - 1] != TerrainType.BUILDING
                        and (x, y) not in self.wmap.characters
                        and (x - 1, y) not in self.wmap.characters):
                    m = build_monster("wolf", (x - 1, y))
                    m.id = "enc_zonefloor"
                    m.metadata["zone"] = zone.name
                    self.engine.npc_manager.add_npc(m)
                    self.assertTrue(self.wmap.move_character(m, x, y),
                                    "floor tiles inside a zone stay walkable")
                    return
        self.skipTest("no adjacent floor pair in this zone")


if __name__ == "__main__":
    unittest.main()
