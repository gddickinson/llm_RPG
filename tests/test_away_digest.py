"""While-you-were-away digest (M.9a) — the returning player is shown what
the autoplay hero did, not left to dig it out of the event log."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_dig_"))

import unittest

from engine.game_engine import GameEngine
from engine.away_digest import build_digest


class TestAwayDigest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _deed(self, text):
        self.engine.memory_manager.add_event(f"[Away] {self.p.name} {text}")

    def test_no_digest_without_an_away_period(self):
        self.assertIsNone(build_digest(self.engine, self.p))

    def test_going_away_stamps_a_snapshot(self):
        self.engine.roster.set_away(self.p, True)
        self.assertIn("away_snapshot", self.p.metadata)

    def test_digest_reports_deeds_and_deltas(self):
        self.engine.roster.set_away(self.p, True)
        self._deed("fell to talking with Brenna.")
        self.p.level += 2
        self.p.gold += 30
        self.engine.world.time += 2 * 24 * 60
        dg = build_digest(self.engine, self.p)
        self.assertIsNotNone(dg)
        title, lines = dg
        blob = " ".join(lines)
        self.assertIn("Brenna", blob)
        self.assertIn("2 level", blob)
        self.assertIn("+30 gold", blob)
        self.assertIn("2 day", blob)

    def test_reports_quests_and_legendary_deeds(self):
        self.engine.roster.set_away(self.p, True)
        self.engine.memory_manager.add_event("Quest accepted: The Burning Road")
        self.engine.memory_manager.add_event(
            "Quest turned in: The Burning Road (+80g, +150xp)")
        self.engine.memory_manager.add_event(
            "[Legend] You cut Vharo Blackbanner down beneath his own standard.")
        blob = " ".join(build_digest(self.engine, self.p)[1])
        self.assertIn("took on 1 quest", blob)
        self.assertIn("saw 1 through", blob)
        self.assertIn("Legendary deeds", blob)
        self.assertIn("Vharo Blackbanner", blob)

    def test_digest_is_one_shot(self):
        self.engine.roster.set_away(self.p, True)
        self._deed("did a thing.")
        self.assertIsNotNone(build_digest(self.engine, self.p))
        self.assertIsNone(build_digest(self.engine, self.p))

    def test_reports_a_new_companion(self):
        from world.monsters import build_monster
        from characters.character_types import CharacterClass
        self.engine.companion_manager.party = []
        self.engine.roster.set_away(self.p, True)
        ally = build_monster("wolf", (0, 0))
        ally.id, ally.name = "kestrel", "Kestrel"
        ally.character_class = CharacterClass("ranger")
        self.engine.npc_manager.add_npc(ally)
        self.engine.companion_manager.party.append("kestrel")
        dg = build_digest(self.engine, self.p)
        self.assertIn("Kestrel", " ".join(dg[1]))

    def test_nothing_happened_is_no_digest(self):
        # away, but no deeds and no changes -> nothing to report
        self.engine.roster.set_away(self.p, True)
        self.assertIsNone(build_digest(self.engine, self.p))


if __name__ == "__main__":
    unittest.main()
