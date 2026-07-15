"""BLD.2 — functional room typing: each BSP leaf is tagged a room_type from the
building's room-set and furnished with that type's kit, so a tavern reads
common-room + bar + kitchen and a smithy forge + workshop (not a size-ranked
bed-and-chest in every room)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

from world import room_plan as RP
from world import room_gen
from world.interiors import Interior
from world.world_map import TerrainType as T


def _build_interior(kind, w=12, h=9, seed=7):
    """A subdivided Interior ready for furnish_typed (mirrors fit_to_footprint)."""
    inter = Interior(name=f"Test {kind}", width=w, height=h)
    inter.init_grid()
    inter.door = (w // 2, h - 1)
    inter.terrain[h - 1][w // 2] = T.ROAD
    grid, rooms = room_gen.subdivide(w, h, seed, min_room=2, max_depth=2)
    grid[h - 2][w // 2] = room_gen.FLOOR
    for y in range(h - 1):
        for x in range(1, w - 1):
            if grid[y][x] == room_gen.WALL:
                inter.terrain[y][x] = T.BUILDING
    return inter, rooms


class TestRoomSet(unittest.TestCase):
    def test_resolves_by_function(self):
        self.assertEqual(RP.room_set_for("forge")[0], "forge")
        self.assertEqual(RP.room_set_for("tavern")[0], "common_room")
        self.assertEqual(RP.room_set_for("temple")[0], "nave")

    def test_resolves_by_kind_then_default(self):
        self.assertEqual(RP.room_set_for("inn")[0], "common_room")
        self.assertEqual(RP.room_set_for("shop")[0], "counter")
        self.assertEqual(RP.room_set_for("zzz-unknown"),
                         RP._room_sets().get("default"))

    def test_single_room_building_has_no_program(self):
        self.assertLess(len(RP.room_set_for("well")), 2)   # gate keeps it 1 room


class TestAssignTypes(unittest.TestCase):
    def test_entrance_room_is_the_public_room(self):
        rooms = [(1, 1, 4, 3), (6, 1, 4, 3), (1, 4, 9, 4)]  # room 3 reaches y=7
        door = (5, 8)                        # inside tile (5, 7) is in room 3
        typed = RP.assign_types(rooms, door, ["common_room", "bar", "kitchen"])
        ent = next(r for r, t in typed if t == "common_room")
        self.assertTrue(ent[0] <= door[0] < ent[0] + ent[2]
                        and ent[1] <= door[1] - 1 < ent[1] + ent[3])

    def test_every_room_gets_a_type(self):
        rooms = [(1, 1, 4, 3), (6, 1, 4, 3), (1, 5, 9, 3), (1, 9, 4, 2)]
        typed = RP.assign_types(rooms, (5, 12), ["a", "b"])
        self.assertEqual(len(typed), len(rooms))


class TestFurnishTyped(unittest.TestCase):
    def _furn(self, kind):
        inter, rooms = _build_interior(kind)
        RP.furnish_typed(inter, rooms, kind, seed=7)
        return inter

    def test_places_furniture_on_floor_only(self):
        inter = self._furn("tavern")
        self.assertTrue(inter.furniture)
        for f in inter.furniture:
            self.assertNotEqual(inter.terrain[f["y"]][f["x"]], T.BUILDING,
                                f"{f} sits on a wall")

    def test_tavern_gets_tavern_furniture(self):
        names = {f["name"] for f in self._furn("tavern").furniture}
        self.assertTrue(names & {"Table", "Bench", "Hearth", "Barrel"},
                        f"a tavern should have common-room furniture: {names}")

    def test_smithy_gets_a_forge(self):
        names = {f["name"] for f in self._furn("forge").furniture}
        self.assertIn("Anvil", names)

    def test_does_not_overcrowd(self):
        inter = self._furn("tavern")
        inner = (inter.width - 2) * (inter.height - 2)
        self.assertLess(len(inter.furniture), inner * 0.6,
                        "rooms should stay roomy")

    def test_sets_an_npc_spot(self):
        inter = self._furn("tavern")
        self.assertTrue(inter.npc_spots)

    def test_deterministic(self):
        a = self._furn("tavern").furniture
        b = self._furn("tavern").furniture
        self.assertEqual([(f["name"], f["x"], f["y"]) for f in a],
                         [(f["name"], f["x"], f["y"]) for f in b])


if __name__ == "__main__":
    unittest.main()
