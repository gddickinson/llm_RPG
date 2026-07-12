"""The NPC social graph (P20.2).

NPC-to-NPC relationships drift every night — same-faction folk and kin
warm, the lawful and the outlaw grate — and cross thresholds on their own
into friendships and feuds, each a [Realm] beat. Peer relationships, not
spokes to the player; heuristic, not the LLM-only director path."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_soc_"))

import unittest

from engine.game_engine import GameEngine
from engine.social_graph import SocialGraph, FRIEND, FEUD
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
        self.S = self.engine.social_graph
        self.S.rng.seed(0)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _npc(self, cid, faction="neutral", cls="merchant"):
        m = build_monster("wolf", (5, 5))
        m.id = cid
        m.name = cid.title()
        m.character_class = CharacterClass(cls)
        m.faction = faction
        m.metadata = {}
        self.engine.npc_manager.add_npc(m)
        return m


class TestDrift(_Base):
    def test_same_faction_bonds(self):
        a = self._npc("goren", "guildA")
        b = self._npc("vera", "guildA")
        self.assertGreater(self.S._drift(a, b), 0)

    def test_lawful_and_outlaw_grate(self):
        g = self._npc("kell", "guards", cls="guard")
        r = self._npc("snag", "brigands", cls="brigand")
        self.assertLess(self.S._drift(g, r), 0)

    def test_strangers_are_not_kin(self):
        a = self._npc("a1", "x")
        b = self._npc("b1", "y")
        self.assertFalse(self.S._kin(a, b))


class TestThresholds(_Base):
    def test_crossing_into_friendship(self):
        a = self._npc("goren", "g")
        b = self._npc("vera", "g")
        a.modify_relationship(b.id, FRIEND)
        b.modify_relationship(a.id, FRIEND)
        line = self.S._threshold(a, b)
        self.assertIsNotNone(line)
        self.assertIn("friends", line)
        self.assertTrue(a.metadata["social"].get(f"friend:{b.id}"))
        self.assertTrue(b.metadata["social"].get(f"friend:{a.id}"),
                        "the bond is mutual")

    def test_crossing_into_feud(self):
        a = self._npc("kell", "guards", cls="guard")
        b = self._npc("snag", "brigands", cls="brigand")
        a.modify_relationship(b.id, FEUD)
        b.modify_relationship(a.id, FEUD)
        line = self.S._threshold(a, b)
        self.assertIsNotNone(line)
        self.assertIn("feud", line)

    def test_a_friendship_is_announced_once(self):
        a = self._npc("goren", "g")
        b = self._npc("vera", "g")
        a.modify_relationship(b.id, FRIEND)
        b.modify_relationship(a.id, FRIEND)
        self.assertIsNotNone(self.S._threshold(a, b))
        self.assertIsNone(self.S._threshold(a, b), "no repeat announcement")


class TestRunDay(_Base):
    def test_run_day_drifts_a_pair(self):
        # a private two-NPC faction so they only have each other
        a = self._npc("solo1", "loners")
        b = self._npc("solo2", "loners")
        before = a.get_relationship(b.id)
        for _ in range(6):
            self.S.run_day()
        self.assertGreater(a.get_relationship(b.id), before,
                           "clanmates warm to each other")

    def test_monsters_stay_out_of_the_graph(self):
        wolf = build_monster("wolf", (7, 7))
        wolf.id = "enc_wolf_soc"
        self.engine.npc_manager.add_npc(wolf)
        for _ in range(5):
            self.S.run_day()
        self.assertNotIn("social", wolf.metadata,
                         "beasts keep no social calendar")

    def test_friends_and_feuds_emerge_over_time(self):
        self.S.rng.seed(3)
        for _ in range(40):
            self.S.run_day()
        friends = feuds = 0
        for n in self.engine.npc_manager.npcs.values():
            soc = (n.metadata or {}).get("social", {})
            friends += sum(1 for k in soc if k.startswith("friend:"))
            feuds += sum(1 for k in soc if k.startswith("feud:"))
        self.assertGreater(friends, 0, "friendships form on their own")
        self.assertGreater(feuds, 0, "and so do feuds")


if __name__ == "__main__":
    unittest.main()
