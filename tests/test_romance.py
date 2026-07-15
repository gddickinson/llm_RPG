"""Romance & rivalry (P20.6) — relationship types, not one scalar.

/court climbs a ladder (courting -> sweetheart -> betrothed -> married)
gated by regard; courting a second while partnered stirs jealousy; a
deeply-soured NPC becomes a rival who won't be wooed. State on metadata."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_rom_"))

import unittest

from engine.game_engine import GameEngine
from engine import romance
from world.monsters import build_monster
from characters.character_types import CharacterClass


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.pid = self.engine.player.id

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _npc(self, cid, cls="villager"):
        n = build_monster("wolf", (5, 5))
        n.id = cid
        n.name = cid.title()
        n.character_class = CharacterClass(cls)
        n.metadata = {}
        self.engine.npc_manager.add_npc(n)
        return n

    def _set(self, npc, rel):
        npc.relationships[self.pid] = rel


class TestLadder(_Base):
    def test_too_cold_is_refused(self):
        n = self._npc("greta")
        self._set(n, 10)
        romance.court(self.engine, n)
        self.assertIsNone(romance.stage_of(n))

    def test_the_ladder_climbs_with_regard(self):
        n = self._npc("goren")
        for rel, stage in ((30, "courting"), (55, "sweetheart"),
                           (72, "betrothed"), (90, "married")):
            self._set(n, rel)
            romance.court(self.engine, n)
            self.assertEqual(romance.stage_of(n), stage)

    def test_marriage_sets_the_spouse(self):
        n = self._npc("goren")
        n.metadata["romance"] = "betrothed"
        self._set(n, 90)
        romance.court(self.engine, n)
        self.assertEqual(romance.spouse_of_player(self.engine).id, n.id)

    def test_cannot_wed_two(self):
        a = self._npc("ann")
        a.metadata["romance"] = "married"
        b = self._npc("bea")
        b.metadata["romance"] = "betrothed"
        self._set(b, 95)
        msg = romance.court(self.engine, b)
        self.assertNotEqual(romance.stage_of(b), "married")
        self.assertIn("already wed", msg)


class TestJealousy(_Base):
    def test_courting_another_cools_the_first(self):
        a = self._npc("ann")
        a.metadata["romance"] = "sweetheart"
        self._set(a, 80)
        b = self._npc("bea")
        b.metadata["romance"] = "courting"     # one more rung -> sweetheart
        self._set(b, 55)
        before = a.get_relationship(self.pid)
        romance.court(self.engine, b)          # b -> sweetheart, a jealous
        self.assertLess(a.get_relationship(self.pid), before)
        self.assertIn("jealous", _recent(self.engine))

    def test_a_strained_marriage_slips(self):
        a = self._npc("ann")
        a.metadata["romance"] = "married"
        self._set(a, 90)
        b = self._npc("bea")
        b.metadata["romance"] = "courting"     # one more rung -> sweetheart
        self._set(b, 55)
        romance.court(self.engine, b)
        self.assertEqual(romance.stage_of(a), "betrothed",
                         "the marriage is strained a rung")


class TestRivalry(_Base):
    def test_a_soured_npc_becomes_a_rival(self):
        n = self._npc("kell", cls="guard")
        self._set(n, -60)
        self.assertTrue(romance.provoke_rival(self.engine, n))
        self.assertTrue(romance.is_rival(n))

    def test_a_rival_will_not_be_wooed(self):
        n = self._npc("kell", cls="guard")
        n.metadata["romance"] = "rival"
        self._set(n, 90)
        romance.court(self.engine, n)
        self.assertEqual(romance.stage_of(n), "rival")

    def test_a_partner_does_not_turn_rival(self):
        n = self._npc("ann")
        n.metadata["romance"] = "sweetheart"
        self._set(n, -60)
        self.assertFalse(romance.provoke_rival(self.engine, n))


class TestUpkeep(_Base):
    def test_a_spouse_provides(self):
        n = self._npc("goren")
        n.metadata["romance"] = "married"
        self.engine.romance.rng.seed(0)
        gold0 = self.engine.player.gold
        for _ in range(6):
            self.engine.romance.run_day()
        self.assertGreater(self.engine.player.gold, gold0)

    def test_a_wedding_enters_the_chronicle(self):
        n = self._npc("goren")
        n.metadata["romance"] = "betrothed"
        self._set(n, 95)
        self.engine.chronicle.entries = []
        romance.court(self.engine, n)
        self.assertTrue(any("wed" in e["text"].lower()
                            for e in self.engine.chronicle.entries),
                        "the [Legend] wedding beat is chronicled")


if __name__ == "__main__":
    unittest.main()
