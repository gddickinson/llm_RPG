"""Regression tests for playtest session 2 findings (P6.8)."""

import unittest

from engine.game_engine import GameEngine
from quests.quest import QuestStatus


class TestPlaytest2Findings(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_every_authored_quest_has_a_ui_turn_in_path(self):
        """Finding: giver '' quests complete but can never be turned in
        through the GUI (dialog turn-in needs giver adjacency)."""
        from characters.npc_presets import NPC_SPECS
        from engine.adventure_tome import adventure_npc_ids
        adv = adventure_npc_ids()
        for qid, quest in self.engine.quest_manager.quests.items():
            if qid.startswith("radiant_"):
                continue
            self.assertTrue(quest.giver_id,
                            f"quest {qid} has no giver")
            # reachable if in the open world, OR a preset NPC seated in a
            # zone (P18.2 castle residents), OR a seeded adventure NPC (P38)
            reachable = (self.engine.npc_manager.get_npc(quest.giver_id)
                         is not None or quest.giver_id in NPC_SPECS
                         or quest.giver_id in adv)
            self.assertTrue(
                reachable,
                f"quest {qid} giver '{quest.giver_id}' not in world")

    def test_tavern_intro_full_gui_flow(self):
        """Greet Goren -> objective completes -> the same NPC offers
        turn-in (ready_for_turn_in returns it)."""
        qm = self.engine.quest_manager
        qm.accept_quest("tavern_intro")
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        px, py = self.player.position
        goren.position = (px + 1, py)
        self.engine.dialog_system.player_to_npc(goren.id, "Hello!")
        quest = qm.get("tavern_intro")
        self.assertEqual(quest.status, QuestStatus.COMPLETED)
        ready = [q.id for q in qm.ready_for_turn_in("tavernkeeper_01")]
        self.assertIn("tavern_intro", ready,
                      "Goren must offer the turn-in in dialog")

    def test_wolf_howl_alert_converges_packmates(self):
        """Session 2 observed beta closing 5 tiles; pin the mechanism."""
        from world.monsters import build_monster
        from llm.providers.heuristic import HeuristicProvider
        provider = HeuristicProvider(seed=1)
        alpha = build_monster("wolf", (10, 10))
        beta = build_monster("wolf", (18, 10))
        # Alpha sees the player and howls
        action = provider.get_npc_action(
            alpha, {"player_position": (11, 10)}, [], "player @")
        self.assertEqual(action["action"], "howl")
        # Router spreads the alert
        self.engine.npc_manager.add_npc(alpha)
        self.engine.npc_manager.add_npc(beta)
        self.engine.player.position = (11, 10)
        self.engine.action_router.process(alpha, action)
        self.assertEqual(beta.metadata.get("alert"), [11, 10])
        # Beta converges
        follow = provider.get_npc_action(
            beta, {"player_position": (11, 10)}, [], "grass")
        self.assertEqual(follow["action"], "move")
        self.assertEqual(follow["target"], "west")


if __name__ == "__main__":
    unittest.main()
