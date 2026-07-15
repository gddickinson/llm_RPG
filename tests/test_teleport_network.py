"""P28.1a — the Wayfarers' Conclave teleport network.

A rune-circle PLATFORM is planted beside each town; a traveller carrying a
common Wayfarer's RING (which the player starts with) stands on one and steps
to any other. Place-to-place travel, landing on safe ground.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_tp_"))

import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager
from world.world_map import TerrainType


class _Base(unittest.TestCase):
    def setUp(self):
        self._flag = _os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        # bulletproof restore: runs even if setUp raises, and always re-asserts
        # the suite default so a leaked flag can't enable adventurers elsewhere
        self.addCleanup(_os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.tn = self.engine.teleport_network
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        if self._flag is not None:
            _os.environ["LLM_RPG_NO_ADVENTURERS"] = self._flag

    def _stand_on(self, platform):
        self.engine.world.map.remove_character(self.p)
        self.p.position = tuple(platform["pos"])
        self.engine.world.map.place_character(self.p, *self.p.position)


class TestSeeding(_Base):
    def test_platforms_are_planted(self):
        self.assertGreaterEqual(len(self.tn.platforms), 2)
        for pf in self.tn.platforms:
            loc = self.engine.world.get_location_at(*pf["pos"])
            self.assertIsNotNone(loc)
            self.assertEqual(loc.get_property("waystone"), pf["id"])

    def test_the_hero_starts_with_a_ring(self):
        self.assertTrue(self.tn.has_ring(self.p))


class TestTravel(_Base):
    def test_platform_at_detects_the_waystone(self):
        pf = self.tn.platforms[0]
        self._stand_on(pf)
        self.assertEqual((self.tn.platform_at(self.p.position) or {}).get("id"),
                         pf["id"])

    def test_destinations_lists_the_others(self):
        pf = self.tn.platforms[0]
        dests = self.tn.destinations(pf["id"])
        self.assertEqual(len(dests), len(self.tn.platforms) - 1)
        self.assertNotIn(pf["id"], [d["id"] for d in dests])

    def test_teleport_moves_you_to_the_destination(self):
        src, dst = self.tn.platforms[0], self.tn.platforms[1]
        self._stand_on(src)
        msg = self.tn.teleport(dst["id"])
        self.assertIn("arrive", msg.lower())
        # landed at/near the destination waystone
        self.assertLessEqual(
            max(abs(self.p.position[0] - dst["pos"][0]),
                abs(self.p.position[1] - dst["pos"][1])), 8)

    def test_arrival_is_on_walkable_ground(self):
        src, dst = self.tn.platforms[0], self.tn.platforms[1]
        self._stand_on(src)
        self.tn.teleport(dst["id"])
        t = self.engine.world.map.terrain[self.p.position[1]][
            self.p.position[0]]
        self.assertNotIn(t, (TerrainType.BUILDING, TerrainType.WATER,
                             TerrainType.MOUNTAIN))

    def test_cannot_teleport_off_a_platform(self):
        # step away from any waystone
        far = self.tn.platforms[0]["pos"]
        self.engine.world.map.remove_character(self.p)
        self.p.position = (far[0] + 12, far[1] + 12)
        self.engine.world.map.place_character(self.p, *self.p.position)
        msg = self.tn.teleport(self.tn.platforms[1]["id"])
        self.assertIn("waystone", msg.lower())

    def test_cannot_teleport_without_a_ring(self):
        # strip the ring from bag AND worn slots
        self.p.inventory = [it for it in self.p.inventory
                            if "teleport" not in getattr(it, "id", "")]
        try:
            from characters.equipment import get_equipment
            eq = get_equipment(self.p)
            for slot, it in list(eq.items()):
                if it and "teleport" in getattr(it, "id", ""):
                    eq[slot] = None
        except Exception:
            pass
        self.assertFalse(self.tn.has_ring(self.p))
        self._stand_on(self.tn.platforms[0])
        msg = self.tn.teleport(self.tn.platforms[1]["id"])
        self.assertIn("ring", msg.lower())


class TestArrivalCollision(_Base):
    """P28.1b — an arrival never STACKS on an occupied platform; it's diverted
    to a close, safe, free tile beside it."""

    def _occupy(self, x, y):
        from world.monsters import build_monster
        n = build_monster("wolf", (x, y))
        self.engine.npc_manager.add_npc(n)
        self.engine.world.map.remove_character(n)
        n.position = (x, y)
        self.engine.world.map.place_character(n, x, y)
        return n

    def test_arrival_diverts_off_an_occupied_waystone(self):
        src, dst = self.tn.platforms[0], self.tn.platforms[1]
        dx, dy = dst["pos"]
        self._occupy(dx, dy)                 # someone standing on the waystone
        self._stand_on(src)
        self.tn.teleport(dst["id"])
        self.assertNotEqual(tuple(self.p.position), (dx, dy),
                            "must not stack onto the occupied waystone")
        # and it landed on a free, walkable tile
        wmap = self.engine.world.map
        self.assertNotIn(wmap.terrain[self.p.position[1]][self.p.position[0]],
                         (TerrainType.BUILDING, TerrainType.WATER,
                          TerrainType.MOUNTAIN))

    def test_two_arrivals_do_not_stack(self):
        src, dst = self.tn.platforms[0], self.tn.platforms[1]
        # first traveller lands
        self._stand_on(src)
        self.tn.teleport(dst["id"])
        first = tuple(self.p.position)
        # a second traveller (jump the player back to the source and arrive
        # again while the first landing tile is now occupied by a marker)
        self._occupy(*first)
        self._stand_on(src)
        self.tn.teleport(dst["id"])
        self.assertNotEqual(tuple(self.p.position), first,
                            "a second arrival takes a different tile")


class TestLandmarkReach(_Base):
    """P37.2 — the network reaches PLACES OF INTEREST, not just the towns."""

    def test_a_guild_hall_gets_a_waystone(self):
        halls = [l for l in self.engine.world.locations
                 if (l.properties or {}).get("guildhall")]
        if not halls:
            self.skipTest("no guild hall in this world")
        names = " ".join(p["name"] for p in self.tn.platforms)
        self.assertTrue(any(h.name in names for h in halls),
                        "a guild hall is linked to the network")

    def test_no_waystone_on_a_named_building(self):
        # the "Village Well" / "Hamlet Chapel" carry a settlement word but are
        # buildings, not towns — they must not get a waystone
        bad = [p for p in self.tn.platforms
               if "well" in p["name"].lower() or "chapel" in p["name"].lower()]
        self.assertEqual(bad, [])

    def test_no_duplicate_settlement_waystones(self):
        # an authored "Oakvale Waystone" must not be doubled by a generic
        # "Oakvale Village Waystone" for the same town
        names = [p["name"] for p in self.tn.platforms]
        for n in names:
            base = n[:-len(" Waystone")] if n.endswith(" Waystone") else n
            twins = [m for m in names if base.split()[0] in m
                     and m != n and "Ruins" not in m and "Guild" not in m]
            self.assertEqual(twins, [], f"{n} is doubled by {twins}")

    def test_waystones_do_not_stack(self):
        pos = [tuple(p["pos"]) for p in self.tn.platforms]
        self.assertEqual(len(pos), len(set(pos)), "no two share a tile")
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                d = (abs(pos[i][0] - pos[j][0])
                     + abs(pos[i][1] - pos[j][1]))
                self.assertGreater(d, 2, "waystones aren't stacked")


class TestNPCUse(_Base):
    """P37.2 — an NPC bearing a ring travels the same rails as the player."""

    def test_an_npc_with_a_ring_can_teleport(self):
        from world.monsters import build_monster
        src, dst = self.tn.platforms[0], self.tn.platforms[1]
        npc = build_monster("wolf", tuple(src["pos"]))   # any Character body
        from items.item_registry import create_item
        try:
            ring = create_item("teleport_ring")
            npc.inventory = [ring]
        except Exception:
            npc.inventory = []
            self.skipTest("no teleport_ring item")
        self.engine.npc_manager.add_npc(npc)
        self.engine.world.map.remove_character(npc)
        npc.position = tuple(src["pos"])
        self.engine.world.map.place_character(npc, *npc.position)
        self.assertTrue(self.tn.has_ring(npc))
        msg = self.tn.teleport_actor(npc, dst["id"])
        self.assertIn("arrive", msg.lower())
        self.assertLessEqual(
            max(abs(npc.position[0] - dst["pos"][0]),
                abs(npc.position[1] - dst["pos"][1])), 8)

    def test_an_npc_without_a_ring_cannot(self):
        from world.monsters import build_monster
        src = self.tn.platforms[0]
        npc = build_monster("wolf", tuple(src["pos"]))
        npc.inventory = []
        self.engine.npc_manager.add_npc(npc)
        self.engine.world.map.remove_character(npc)
        npc.position = tuple(src["pos"])
        self.engine.world.map.place_character(npc, *npc.position)
        msg = self.tn.teleport_actor(npc, self.tn.platforms[1]["id"])
        self.assertIn("ring", msg.lower())


class TestPlayerHook(_Base):
    """P37.1 — the player-facing hook: stand on a waystone with a ring, a menu
    lists the other waystones, a number key steps you there."""

    def test_can_use_gates_on_platform_and_ring(self):
        self.assertFalse(self.tn.can_use(self.p), "not on a waystone yet")
        self._stand_on(self.tn.platforms[0])
        self.assertTrue(self.tn.can_use(self.p), "on a waystone, ring in bag")

    def test_overlay_lists_numbered_destinations(self):
        here = self.tn.platforms[0]
        self._stand_on(here)
        lines = self.tn.overlay_lines()
        self.assertIn("[1]", "\n".join(lines))
        numbered = [ln for ln in lines if ln.strip().startswith("[")
                    and "Esc" not in ln]
        shown = " ".join(numbered)
        # every OTHER waystone (up to the 9-cap) is offered, and never itself
        for pf in self.tn.destinations(here["id"])[:9]:
            self.assertIn(pf["name"], shown)
        self.assertFalse(any(here["name"] in ln for ln in numbered),
                         "the current waystone is never a destination")

    def test_overlay_asks_for_a_ring_when_missing(self):
        self.p.inventory = [it for it in self.p.inventory
                            if "teleport" not in getattr(it, "id", "")]
        try:
            from characters.equipment import get_equipment
            for slot, it in list(get_equipment(self.p).items()):
                if it and "teleport" in getattr(it, "id", ""):
                    get_equipment(self.p)[slot] = None
        except Exception:
            pass
        self._stand_on(self.tn.platforms[0])
        self.assertIn("ring", " ".join(self.tn.overlay_lines()).lower())

    def test_teleport_index_travels(self):
        src = self.tn.platforms[0]
        self._stand_on(src)
        dst = self.tn.destinations(src["id"])[0]
        msg = self.tn.teleport_index(0)
        self.assertIn("arrive", msg.lower())
        self.assertLessEqual(
            max(abs(self.p.position[0] - dst["pos"][0]),
                abs(self.p.position[1] - dst["pos"][1])), 8)

    def test_teleport_index_rejects_out_of_range(self):
        self._stand_on(self.tn.platforms[0])
        self.assertIn("no such", self.tn.teleport_index(99).lower())


class TestPersistence(_Base):
    def test_platforms_survive_a_save(self):
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            ids = sorted(p["id"] for p in self.tn.platforms)
            sm.save(self.engine, name="tp")
            eng2 = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
            sm.load(eng2, name="tp")
            self.assertEqual(
                sorted(p["id"] for p in eng2.teleport_network.platforms), ids)
            eng2.end_game()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
