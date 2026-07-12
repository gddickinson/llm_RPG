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
