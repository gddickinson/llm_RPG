"""Audit fix (A-train): guild-hall skill TRAINING is now reachable via /train.

`guildhalls.train()` was a complete gold->skill-XP service with no player
trigger. Now a `/train <skill>` dialog command (at a hall, talking to anyone)
reaches it, with a bare `/train` listing the trainable skills + fees.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_train_"))

import unittest

from engine.skill_progression import get_skill_level, total_xp_for_level


class TestGuildTraining(unittest.TestCase):
    def setUp(self):
        # guild halls only seed when adventurers are enabled
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        from engine.game_engine import GameEngine
        self.eng = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
        self.eng.start_game()
        self.hall = self.eng.guildhalls.halls[0]
        hx, hy = self.hall["pos"]
        self.eng.player.position = (hx, hy)
        self.eng.player.gold = 500
        # an NPC to talk to, adjacent, at the hall
        self.npc = next(iter(self.eng.npc_manager.npcs.values()))
        self.npc.position = (hx + 1, hy)

    def tearDown(self):
        try:
            self.eng.end_game()
        except Exception:
            pass

    def _say(self, msg):
        return self.eng.dialog_system.player_to_npc(self.npc.id, msg)

    def test_hall_here_detects_the_hall(self):
        self.assertTrue(self.eng.guildhalls.hall_here(self.eng))

    def test_train_spends_gold_and_adds_skill_xp(self):
        from engine.skill_progression import _skills_dict
        before_xp = _skills_dict(self.eng.player).get("mining", 0)
        before_gold = self.eng.player.gold
        msg = self._say("/train mining")
        self.assertIn("train", msg.lower())
        self.assertLess(self.eng.player.gold, before_gold, "the fee is paid")
        after_xp = _skills_dict(self.eng.player).get("mining", 0)
        self.assertGreater(after_xp, before_xp, "the lesson grants XP")

    def test_bare_train_lists_the_skills(self):
        summary = self._say("/train")
        self.assertIn("/train", summary)
        self.assertIn("mining", summary.lower())
        self.assertNotIn("&lt;", summary, "no HTML escaping in the hint")

    def test_unknown_skill_is_rejected(self):
        self.assertIn("no trainer", self._say("/train flying").lower())

    def test_cannot_train_away_from_a_hall(self):
        self.eng.player.position = (2, 2)
        self.npc.position = (2, 3)
        self.assertIn("guild hall", self._say("/train mining").lower())


if __name__ == "__main__":
    unittest.main()
