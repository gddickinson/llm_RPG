"""Tests for the families and gossip systems."""

import unittest
import random

from characters.families import family_of, relation_to, FAMILIES
from characters.gossip import (
    random_gossip, gossip_for, STATIC_GOSSIP,
    fresh_gossip_about_npcs,
)
from engine.game_engine import GameEngine


class TestFamilies(unittest.TestCase):
    def test_family_lookup(self):
        fam = family_of("tavernkeeper_01")
        self.assertIsNotNone(fam)
        self.assertEqual(fam.surname, "Brindle")

    def test_unknown_npc(self):
        self.assertIsNone(family_of("nonsense"))

    def test_relations(self):
        self.assertEqual(
            relation_to("tavernkeeper_01", "hamlet_innkeeper_01"),
            "my spouse")
        self.assertEqual(
            relation_to("tavernkeeper_01", "minstrel_01"),
            "my sibling")
        self.assertEqual(
            relation_to("tavernkeeper_01", "guard_01"),
            "")

    def test_family_table_consistent(self):
        # Symmetric spouse references
        for npc_id, fam in FAMILIES.items():
            if fam.spouse:
                self.assertIn(
                    fam.spouse, FAMILIES,
                    f"{npc_id} spouse {fam.spouse} missing")
                self.assertEqual(
                    FAMILIES[fam.spouse].spouse, npc_id,
                    f"Spouse symmetry broken: {npc_id} <-> {fam.spouse}")


class TestGossip(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_random_gossip(self):
        rng = random.Random(0)
        line = random_gossip(rng)
        self.assertIn(line, STATIC_GOSSIP)

    def test_gossip_for_returns_lines(self):
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        lines = gossip_for(goren, self.engine, max_lines=2)
        self.assertTrue(lines)

    def test_fresh_gossip_about_npcs(self):
        # Seed the memory log
        self.engine.memory_manager.add_event(
            "Karim was seen patrolling the road.")
        hits = fresh_gossip_about_npcs(
            self.engine.memory_manager, "tavernkeeper_01",
            ["Karim"], max_lines=2)
        self.assertTrue(hits)
        self.assertIn("Karim", hits[0])


if __name__ == "__main__":
    unittest.main()
