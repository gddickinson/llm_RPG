"""Per-NPC memory retrieval + reflection tests (P3.2)."""

import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from engine.npc_memory import (
    remember, retrieve, log_exchange, recent_exchanges, opinions,
    nightly_reflection, MAX_DIALOG_LOG, MAX_OPINIONS,
)


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.npc.memories = []

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_relevance_beats_recency(self):
        now = self.engine.world.time
        remember(self.npc, "The troll Gorkash ambushed a caravan",
                 3, now - 500)
        remember(self.npc, "I polished the tavern mugs", 1, now)
        top = retrieve(self.npc, "tell me about the troll", now, k=1)
        self.assertIn("Gorkash", top[0])

    def test_recency_breaks_ties(self):
        now = self.engine.world.time
        remember(self.npc, "A quiet morning in the tavern", 2,
                 now - 10 * 24 * 60)
        remember(self.npc, "A busy evening in the tavern", 2, now)
        top = retrieve(self.npc, "how is business?", now, k=1)
        self.assertIn("busy evening", top[0])

    def test_importance_matters(self):
        now = self.engine.world.time
        remember(self.npc, "Someone sneezed", 1, now)
        remember(self.npc, "Bandits threatened to burn the tavern", 9, now)
        top = retrieve(self.npc, "anything new?", now, k=1)
        self.assertIn("Bandits", top[0])

    def test_legacy_wallclock_memories_still_retrievable(self):
        self.npc.add_memory("An old tale about a dragon", 3)  # legacy path
        top = retrieve(self.npc, "tell me about the dragon",
                       self.engine.world.time, k=1)
        self.assertIn("dragon", top[0])


class TestDialogLogAndReflection(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.npc = self.engine.npc_manager.get_npc("tavernkeeper_01")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_dialog_log_capped_at_ten(self):
        for i in range(15):
            log_exchange(self.npc, f"q{i}", f"a{i}")
        log = self.npc.metadata["dialog_log"]
        self.assertEqual(len(log), MAX_DIALOG_LOG)
        self.assertEqual(log[-1]["player"], "q14")
        self.assertEqual(log[0]["player"], "q5")

    def test_talking_populates_memory_and_log(self):
        px, py = self.engine.player.position
        self.npc.position = (px + 1, py)
        self.engine.dialog_system.player_to_npc(self.npc.id, "Fine ale!")
        self.assertTrue(any("Fine ale!" in m.get("event", "")
                            for m in self.npc.memories))
        self.assertTrue(recent_exchanges(self.npc))

    def test_heuristic_reflection_creates_opinion(self):
        now = self.engine.world.time
        self.npc.metadata["reflected_upto"] = len(self.npc.memories)
        remember(self.npc, "The player saved my sister", 8, now)
        remember(self.npc, "The player bought three rounds", 4, now)
        remember(self.npc, "The player asked about the troll", 2, now)
        reflected = nightly_reflection(self.engine)
        self.assertGreaterEqual(reflected, 1)
        ops = opinions(self.npc)
        self.assertTrue(ops)
        self.assertIn("saved my sister", ops[-1])

    def test_llm_reflection_uses_provider(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value="I trust this adventurer with my life.")
        now = self.engine.world.time
        self.npc.metadata["reflected_upto"] = len(self.npc.memories)
        for i in range(3):
            remember(self.npc, f"event {i}", 3, now)
        nightly_reflection(self.engine)
        self.assertIn("I trust this adventurer with my life.",
                      opinions(self.npc))

    def test_opinions_capped(self):
        now = self.engine.world.time
        for round_no in range(5):
            self.npc.metadata["reflected_upto"] = len(self.npc.memories)
            for i in range(3):
                remember(self.npc, f"r{round_no} e{i}", 3, now)
            nightly_reflection(self.engine)
        self.assertLessEqual(len(opinions(self.npc)), MAX_OPINIONS)

    def test_day_change_triggers_reflection(self):
        now = self.engine.world.time
        self.npc.metadata["reflected_upto"] = len(self.npc.memories)
        for i in range(3):
            remember(self.npc, f"daily event {i}", 5, now)
        # Cross a day boundary
        self.engine.world.time = ((now // (24 * 60)) + 1) * 24 * 60
        self.engine.advance_turn()
        self.assertTrue(opinions(self.npc))

    def test_prompt_includes_retrieved_memory_and_opinion(self):
        from engine.dialog_protocol import build_prompt
        now = self.engine.world.time
        remember(self.npc, "The player slew the troll Gorkash", 8, now)
        self.npc.metadata["opinions"] = ["I owe the player a debt."]
        log_exchange(self.npc, "Hello", "Welcome!")
        prompt = build_prompt(self.engine, self.npc,
                              "What do you think of the troll?", [])
        self.assertIn("Gorkash", prompt)
        self.assertIn("I owe the player a debt.", prompt)
        self.assertIn("Welcome!", prompt)

    def test_memory_persists_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        now = self.engine.world.time
        remember(self.npc, "A memorable rescue", 7, now)
        log_exchange(self.npc, "hi", "ho")
        self.npc.metadata["opinions"] = ["The player is brave."]
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="m")
            self.assertTrue(sm.load(self.engine, name="m"))
            npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
            self.assertTrue(any("memorable rescue" in m.get("event", "")
                                for m in npc.memories))
            self.assertEqual(npc.metadata["opinions"],
                             ["The player is brave."])
            self.assertTrue(npc.metadata["dialog_log"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
