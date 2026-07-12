"""Puzzles II (P21.3) — levers/gates and item-fit altars.

Beyond the single sigil ward: a lever-gate (throw the levers into the
right pattern to open a warded passage) and an altar item-fit (lay the
thing it hungers for upon it). Both gate stairs like the sigils; a plain
prayer-altar still prays."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_puz_"))

import types
import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.S = self.engine.structures

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestLever(_Base):
    def _gate(self):
        return types.SimpleNamespace(
            name="Vault Gate",
            puzzle={"kind": "lever", "pattern": [0, 2], "wards": "down"})

    def test_the_right_pattern_opens_the_gate(self):
        z = self._gate()
        self.assertTrue(self.S.stairs_warded(z, up=False))
        self.S.pull_lever(z, {"idx": 0})
        self.S.pull_lever(z, {"idx": 2})
        self.assertIn(z.name, self.S.solved)
        self.assertFalse(self.S.stairs_warded(z, up=False))

    def test_a_wrong_pattern_holds(self):
        z = self._gate()
        self.S.pull_lever(z, {"idx": 0})
        self.S.pull_lever(z, {"idx": 1})       # wrong lever up
        self.assertNotIn(z.name, self.S.solved)
        self.assertTrue(self.S.stairs_warded(z, up=False))

    def test_toggling_off_a_wrong_lever_recovers(self):
        z = self._gate()
        self.S.pull_lever(z, {"idx": 0})
        self.S.pull_lever(z, {"idx": 1})       # {0,1}
        self.S.pull_lever(z, {"idx": 1})       # toggle 1 back -> {0}
        self.S.pull_lever(z, {"idx": 2})       # {0,2} == pattern
        self.assertIn(z.name, self.S.solved)


class TestAltar(_Base):
    def _altar(self):
        return types.SimpleNamespace(
            name="Sun Altar",
            puzzle={"kind": "altar", "requires": "greater_potion",
                    "wards": "up"})

    def test_the_offering_dissolves_the_ward(self):
        z = self._altar()
        self.engine.player.inventory.append(create_item("greater_potion"))
        self.S.offer_at_altar(z, {})
        self.assertIn(z.name, self.S.solved)
        self.assertFalse(any(getattr(i, "id", "") == "greater_potion"
                             for i in self.engine.player.inventory),
                         "the offering is consumed")

    def test_empty_handed_the_ward_holds(self):
        z = self._altar()
        self.S.offer_at_altar(z, {})
        self.assertNotIn(z.name, self.S.solved)


class TestFurnitureRouting(_Base):
    def _interior(self, furniture, puzzle=None):
        z = types.SimpleNamespace(name="Test Room", furniture=furniture,
                                  puzzle=puzzle)
        self.engine.current_interior = z
        self.engine.player.position = (3, 3)
        return z

    def test_a_lever_routes_to_pull(self):
        self._interior([{"name": "Lever", "x": 3, "y": 3, "idx": 0}],
                       puzzle={"kind": "lever", "pattern": [0], "wards": "up"})
        from engine.furniture import interact
        msg = interact(self.engine)
        self.assertIsNotNone(msg)
        self.assertIn("Test Room", self.S.solved, "pulling the one lever won")

    def test_a_plain_altar_still_prays(self):
        # an altar with NO altar-puzzle must fall through to prayer,
        # not be swallowed by the item-fit branch
        self._interior([{"name": "Altar", "x": 3, "y": 3}], puzzle=None)
        from engine.furniture import interact
        msg = interact(self.engine)
        self.assertIsNotNone(msg)
        self.assertNotIn("bare, cold stone", msg,
                         "a plain altar prays, it isn't an offering puzzle")


class TestContent(_Base):
    def test_the_keep_has_a_lever_gate(self):
        from world.structures import STRUCTURES
        hall = None
        for lv in STRUCTURES["ruined_keep"]["levels"]:
            inter = self.S._build_level(lv, "ruined_keep")
            if "Great Hall" in inter.name:
                hall = inter
        self.assertIsNotNone(hall)
        levers = [f for f in hall.furniture if f["name"] == "Lever"]
        self.assertEqual(len(levers), 3)
        self.assertEqual(hall.puzzle.get("kind"), "lever")
        self.assertTrue(self.S.stairs_warded(hall, up=False),
                        "the descent is warded until the levers are set")


class TestPersistence(_Base):
    def test_lever_state_round_trips(self):
        z = types.SimpleNamespace(
            name="Gate", puzzle={"kind": "lever", "pattern": [0, 1],
                                 "wards": "up"})
        self.S.pull_lever(z, {"idx": 0})        # partial progress
        d = self.S.to_dict()
        self.assertIn("Gate", d["lever_state"])
        from world.structures import StructureBuilder
        restored = StructureBuilder(self.engine)
        restored.from_dict(d)
        self.assertEqual(restored.lever_state.get("Gate"), [0])


if __name__ == "__main__":
    unittest.main()
