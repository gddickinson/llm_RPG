"""Bloodstone Castle's living cast (P18.2): the royal family, staff,
courtiers and garrison seat into the castle zones as friendly residents."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from characters.npc_presets import NPC_SPECS, all_presets
from engine.game_engine import GameEngine
from engine.presence import npc_adjacent_to_player
from world.location import Location
from world.structures import StructureBuilder


CAST = ["king_bloodstone", "queen_bloodstone", "heir_bloodstone",
        "duke_voss", "steward_bloodstone", "cook_bloodstone",
        "maid_bloodstone", "stablehand_bloodstone", "bard_bloodstone",
        "chaplain_bloodstone", "captain_bloodstone",
        "guard_bloodstone_1", "guard_bloodstone_2"]


class TestCastData(unittest.TestCase):
    def test_the_whole_court_is_authored(self):
        for nid in CAST:
            self.assertIn(nid, NPC_SPECS, f"{nid} preset missing")
            self.assertTrue(NPC_SPECS[nid].get("zone_bound"),
                            f"{nid} should be zone-bound")

    def test_court_intrigue_is_seeded_in_relationships(self):
        # the ambitious duke and the heir are at odds — the plot's germ
        self.assertLess(NPC_SPECS["duke_voss"]["relationships"]
                        ["heir_bloodstone"], 0)
        self.assertGreater(NPC_SPECS["king_bloodstone"]["relationships"]
                           ["queen_bloodstone"], 0)


class TestSeating(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.engine.world.locations.append(
            Location("Bloodstone Castle", "A fortress.", 10, 10, 8, 8))
        self.builder = StructureBuilder(self.engine)
        self.builder.build()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _to_crypt(self):
        z = self.engine.interiors["Bloodstone Castle"]
        while getattr(z, "level_below", None) is not None:
            z = z.level_below
        return z

    def test_residents_are_not_in_the_open_world(self):
        # zone-bound cast never joins the demo roster
        world_ids = {n.id for n in all_presets()}
        for nid in CAST:
            self.assertNotIn(nid, world_ids)
        self.assertIsNone(self.engine.npc_manager.get_npc("king_bloodstone"))

    def test_entering_the_hall_seats_the_royal_court(self):
        hall = self.engine.interiors["Bloodstone Castle"]
        self.builder.on_enter_level(hall)
        king = self.engine.npc_manager.get_npc("king_bloodstone")
        self.assertIsNotNone(king, "the King holds his hall")
        self.assertEqual(king.metadata.get("zone"), hall.name)
        self.assertTrue(king.metadata.get("resident"))
        seated = sum(1 for n in self.engine.npc_manager.npcs.values()
                     if n.metadata.get("resident"))
        self.assertGreaterEqual(seated, 6, "a full court, not one man")

    def test_the_king_is_talkable_at_his_post(self):
        hall = self.engine.interiors["Bloodstone Castle"]
        self.builder.on_enter_level(hall)
        king = self.engine.npc_manager.get_npc("king_bloodstone")
        self.engine.current_interior = hall
        self.engine.player.position = (king.position[0] + 1,
                                       king.position[1])
        self.assertTrue(npc_adjacent_to_player(self.engine, king))

    def test_re_entering_does_not_duplicate_the_court(self):
        hall = self.engine.interiors["Bloodstone Castle"]
        self.builder.on_enter_level(hall)
        n1 = len(self.engine.npc_manager.npcs)
        self.builder.on_enter_level(hall)      # walk out and back
        self.assertEqual(len(self.engine.npc_manager.npcs), n1,
                         "no ghostly second King")

    def test_the_crypt_still_holds_the_dead_alongside_residents(self):
        crypt = self._to_crypt()
        roused = self.builder.on_enter_level(crypt)
        self.assertGreaterEqual(roused, 1, "the dead keep watch")


if __name__ == "__main__":
    unittest.main()
