"""Topic journal tests (P3.6)."""

import unittest

from engine.game_engine import GameEngine
from engine.topics import TOPICS


class TestTopicJournal(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.tj = self.engine.topic_journal
        self.goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.karim = self.engine.npc_manager.get_npc("guard_01")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_hearing_a_keyword_unlocks_topic(self):
        self.assertNotIn("gorkash", self.tj.known())
        self.engine.memory_manager.add_event(
            'Karim says: "Gorkash has been raiding again."')
        self.assertIn("gorkash", self.tj.known())
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-2:])
        self.assertIn("New topic", log)

    def test_saying_a_keyword_does_not_self_teach(self):
        self.engine.memory_manager.add_event(
            'You say to Goren: "Tell me about Gorkash"')
        self.assertNotIn("gorkash", self.tj.known())

    def test_learned_once_no_duplicates(self):
        self.engine.memory_manager.add_event("Gorkash roars.")
        self.engine.memory_manager.add_event("Gorkash roars again.")
        self.assertEqual(self.tj.known().count("gorkash"), 1)

    def test_asking_known_topic_gets_authored_answer(self):
        self.tj.known().append("gorkash")
        px, py = self.player.position
        self.karim.position = (px + 1, py)
        reply = self.engine.dialog_system.player_to_npc(
            self.karim.id, "What can you tell me about Gorkash?")
        self.assertIn("hunt", reply.lower())

    def test_unknown_topic_gets_no_answer(self):
        px, py = self.player.position
        self.karim.position = (px + 1, py)
        reply = self.engine.dialog_system.player_to_npc(
            self.karim.id, "What about the mithril?")
        self.assertNotIn("east shaft", reply.lower())
        # (also must not unlock it — saying isn't hearing)
        self.assertNotIn("mithril", self.tj.known())

    def test_default_response_for_npc_without_authored_line(self):
        self.tj.known().append("mithril")
        melody = self.engine.npc_manager.get_npc("minstrel_01")
        line = self.tj.npc_response(melody, "mithril")
        self.assertIn("fairy tale", line)

    def test_llm_prompt_grounds_raised_topics(self):
        from engine.dialog_protocol import build_prompt
        self.tj.known().append("silver_blade")
        prompt = build_prompt(self.engine, self.goren,
                              "Tell me about the silver blade", [])
        self.assertIn("TOPICS THE PLAYER RAISED", prompt)
        self.assertIn("never returned", prompt)
        # Unraised topics stay out of the prompt
        self.assertNotIn("east shaft", prompt.lower())

    def test_secret_reveal_teaches_topics(self):
        # Goren's secret mentions the silver blade recipe
        self.goren.modify_relationship(self.player.id, 20)
        from engine.secrets import reveal
        reveal(self.engine, self.goren, "goren_troll_silver")
        self.assertIn("silver_blade", self.tj.known())

    def test_overlay_lists_known_topics(self):
        # NB: world-gen lore lines may legitimately pre-teach topics
        self.tj.known().append("ruined_keep")
        count = len(self.tj.known())
        lines = self.tj.overlay_lines()
        text = "\n".join(lines)
        self.assertIn("The Ruined Keep", text)
        self.assertIn(f"{count}/{len(TOPICS)}", text)

    def test_topics_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.tj.known().append("bandits")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="tp")
            self.player.metadata["topics_known"] = []
            self.assertTrue(sm.load(self.engine, name="tp"))
            self.assertIn("bandits",
                          self.engine.topic_journal.known())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
