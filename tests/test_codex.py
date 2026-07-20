"""The self-teaching Field Guide (GAP.2): entries auto-unlock from the
event log, teaching the player a system the first time they meet it."""

import tempfile
import unittest

from engine.game_engine import GameEngine


class TestCodex(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.codex = self.engine.codex

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_entries_loaded(self):
        self.assertGreater(len(self.codex.entries), 15)

    def test_start_entries_auto_unlock_silently(self):
        got, total = self.codex.counts()
        self.assertGreaterEqual(got, 3)               # welcome/collection/...
        self.assertTrue(self.codex.is_unlocked("welcome"))
        # start unlocks are silent — no [Codex] beat spam
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertNotIn("[Codex] New journal entry: Your Field Journal", log)

    def test_trigger_unlocks_and_announces(self):
        # obscure systems auto-unlock the first time you meet them
        self.assertFalse(self.codex.is_unlocked("enchanting"))
        before = self.codex.unseen()
        self.engine.memory_manager.add_event("You enchant your blade.")
        self.assertTrue(self.codex.is_unlocked("enchanting"))
        self.assertGreater(self.codex.unseen(), before)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("[Codex] New journal entry: Enchanting", log)

    def test_no_double_unlock(self):
        self.engine.memory_manager.add_event("[Build] You raise a wall.")
        self.assertTrue(self.codex.is_unlocked("building"))
        n1 = self.codex._store().count("building")
        self.engine.memory_manager.add_event("[Build] You level the ground.")
        self.assertEqual(self.codex._store().count("building"), n1)

    def test_codex_lines_do_not_self_trigger(self):
        # a [Codex] beat must never recurse into another unlock
        self.engine.memory_manager.add_event(
            "[Codex] New journal entry: Enchanting — You enchant gear.")
        # 'enchant' is in the text but a [Codex] line is ignored
        self.assertFalse(self.codex.is_unlocked("enchanting"))

    def test_overlay_lines_and_mark_seen(self):
        self.engine.memory_manager.add_event("You persuade the guard.")
        self.assertGreater(self.codex.unseen(), 0)
        lines = self.codex.overlay_lines()
        text = "\n".join(lines)
        self.assertIn("Field Guide", text)
        self.assertIn("Social Checks", text)
        self.assertEqual(self.codex.unseen(), 0, "opening clears the nudge")

    def test_unlocks_persist_through_save(self):
        self.engine.memory_manager.add_event("[Build] You raise a wall.")
        self.assertTrue(self.codex.is_unlocked("building"))
        path = tempfile.mkdtemp() + "/s.json"
        self.engine.save_game(path)
        eng2 = GameEngine(llm_provider="heuristic",
                          enable_npc_processes=False)
        eng2.load_game(path)
        self.assertIn("building", eng2.player.metadata.get("codex", []))
        self.assertTrue(eng2.codex.is_unlocked("building"))
        try:
            eng2.end_game()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
