"""Runtime history — the saga accrues (P20.5).

A Chronicle observes the event log and writes the age-shaping beats — the
[Legend] deaths and the weightiest [Realm] wars/alliances/divine acts —
into a dated saga readable in the Y-journal. It persists."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_chr_"))

import unittest

from engine.game_engine import GameEngine
from engine.chronicle import Chronicle, MAX_ENTRIES


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.C = self.engine.chronicle
        self.C.entries = []              # start from a clean saga

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestWorthiness(_Base):
    def test_legend_events_are_worthy(self):
        self.assertTrue(self.C._worthy("[Legend] A nemesis falls at last."))

    def test_saga_realm_beats_are_worthy(self):
        self.assertTrue(self.C._worthy(
            "[Realm] The brigands and the guards are at war."))
        self.assertTrue(self.C._worthy(
            "[Realm] The gods contend in the heavens."))

    def test_mundane_realm_beats_are_not(self):
        self.assertFalse(self.C._worthy(
            "[Realm] A caravan carried 4 bread from Oakvale to Riverside."))
        self.assertFalse(self.C._worthy("You forage some herbs."))


class TestRecord(_Base):
    def test_a_worthy_event_is_dated_and_cleaned(self):
        self.C.record("[Legend] The dragon of the high roost is slain.")
        self.assertEqual(len(self.C.entries), 1)
        e = self.C.entries[0]
        self.assertNotIn("[", e["text"], "the prefix is stripped")
        self.assertIn("dragon", e["text"])
        self.assertIn("day", e)

    def test_mundane_events_are_ignored(self):
        self.C.record("[Realm] A caravan carried grain to Riverside.")
        self.assertEqual(self.C.entries, [])

    def test_consecutive_duplicates_are_ignored(self):
        self.C.record("[Legend] A tyrant is slain.")
        self.C.record("[Legend] A tyrant is slain.")
        self.assertEqual(len(self.C.entries), 1)

    def test_the_saga_is_capped(self):
        for i in range(MAX_ENTRIES + 15):
            self.C.record(f"[Legend] Champion {i} falls at last.")
        self.assertLessEqual(len(self.C.entries), MAX_ENTRIES)

    def test_the_observer_is_wired(self):
        before = len(self.C.entries)
        self.engine.memory_manager.add_event(
            "[Realm] The guards and the merchants have sworn an alliance.")
        self.assertEqual(len(self.C.entries), before + 1,
                         "add_event feeds the chronicle automatically")


class TestJournalAndPersistence(_Base):
    def test_lines_render_the_saga(self):
        self.C.record("[Legend] A wyrm is slain.")
        lines = self.C.lines()
        self.assertTrue(any("Chronicle of the Age" in ln for ln in lines))
        self.assertTrue(any("wyrm" in ln for ln in lines))

    def test_empty_saga_shows_nothing(self):
        self.assertEqual(self.C.lines(), [])

    def test_round_trip(self):
        self.C.record("[Legend] A nemesis returns to hunt you.")
        d = self.C.to_dict()
        restored = Chronicle(self.engine)
        restored.from_dict(d)
        self.assertEqual(restored.entries, self.C.entries)


if __name__ == "__main__":
    unittest.main()
