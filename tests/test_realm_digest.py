"""T2.3 — the 'State of the Realm' digest surfaces the live sim."""

import unittest

from engine import realm_digest


class _Eng:
    def __init__(self):
        self.faction_ticker = type("F", (), {"state": {
            "villagers": {"strength": 60}, "brigands": {"strength": 25}}})()
        self.monster_tribes = type("T", (), {
            "strength": {"gorge_goblins": 75, "crag_trolls": 20},
            "_tribes": lambda self: {
                "gorge_goblins": {"name": "The Gorge Goblins"},
                "crag_trolls": {"name": "The Crag Trolls"}}})()
        self.nemesis = type("N", (), {"nemeses": {
            "n1": {"name": "Grukk", "title": "the Cleaver"}}})()


class TestRealmDigest(unittest.TestCase):
    def test_digest_summarizes_the_sim(self):
        joined = " ".join(realm_digest.lines(_Eng()))
        self.assertIn("State of the Realm", joined)
        self.assertIn("The Townsfolk", joined)
        self.assertIn("strong", joined)                    # villagers @60
        self.assertIn("The Gorge Goblins", joined)
        self.assertIn("massing to raid", joined)           # @75 threat
        self.assertIn("Grukk the Cleaver", joined)
        self.assertIn("hunts you", joined)

    def test_empty_world_is_quiet(self):
        class _Empty:
            pass
        self.assertIn("All is quiet across the realm.",
                      " ".join(realm_digest.lines(_Empty())))


if __name__ == "__main__":
    unittest.main()
