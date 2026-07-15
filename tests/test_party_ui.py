"""Tests for companion recruitment reachability (P key + trust building).

The audit found engine.recruit() had no UI caller, and — worse — the player
had no way to raise any NPC's relationship to the >=30 recruit threshold.
These tests cover the new P-key toggle and both trust-building paths
(conversation, quest turn-in).
"""

import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from engine.game_engine import GameEngine
from ui.input_handler import InputHandler


class FakeEvent:
    def __init__(self, key):
        self.type = pygame.KEYDOWN
        self.key = key
        self.unicode = ""


def _recruitable_npc(engine):
    for npc in engine.npc_manager.npcs.values():
        klass = getattr(npc.character_class, "value", "")
        if klass in ("warrior", "bard", "cleric", "wizard", "ranger",
                     "paladin") and npc.is_active():
            return npc
    return None


class TestPartyToggle(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.gui = MagicMock()
        self.gui.mode = "play"
        self.handler = InputHandler(self.engine, self.gui)
        self.npc = _recruitable_npc(self.engine)
        if self.npc is None:
            self.skipTest("no recruitable NPC in demo world")
        px, py = self.engine.player.position
        self.npc.position = (px + 1, py)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_p_recruits_trusted_adjacent_npc(self):
        self.npc.modify_relationship(self.engine.player.id, 50)
        self.handler.handle_event(FakeEvent(pygame.K_p))
        self.assertIn(self.npc.id, self.engine.companion_manager.party)

    def test_p_refuses_untrusted_npc_with_reason(self):
        self.handler.handle_event(FakeEvent(pygame.K_p))
        self.assertNotIn(self.npc.id, self.engine.companion_manager.party)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("trust", log.lower())

    def test_p_dismisses_party_member(self):
        self.npc.modify_relationship(self.engine.player.id, 50)
        self.engine.recruit(self.npc.id)
        self.assertIn(self.npc.id, self.engine.companion_manager.party)
        self.handler.handle_event(FakeEvent(pygame.K_p))
        self.assertNotIn(self.npc.id, self.engine.companion_manager.party)


class TestTrustBuilding(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_talking_raises_relationship(self):
        npc = _recruitable_npc(self.engine)
        if npc is None:
            self.skipTest("no recruitable NPC")
        px, py = self.engine.player.position
        npc.position = (px + 1, py)
        before = npc.get_relationship(self.engine.player.id)
        self.engine.dialog_system.player_to_npc(npc.id, "Hello friend!")
        after = npc.get_relationship(self.engine.player.id)
        self.assertGreater(after, before)

    def test_hostile_npc_gains_no_trust_from_talk(self):
        hostile = None
        for npc in self.engine.npc_manager.npcs.values():
            klass = getattr(npc.character_class, "value", "")
            if klass in ("brigand", "troll", "monster") and npc.is_active():
                hostile = npc
                break
        if hostile is None:
            self.skipTest("no hostile NPC")
        px, py = self.engine.player.position
        hostile.position = (px + 1, py)
        before = hostile.get_relationship(self.engine.player.id)
        self.engine.dialog_system.player_to_npc(hostile.id, "Please like me")
        self.assertEqual(
            hostile.get_relationship(self.engine.player.id), before)

    def test_quest_turn_in_raises_giver_relationship(self):
        qm = self.engine.quest_manager
        if not qm:
            self.skipTest("quests disabled")
        quest = None
        for q in qm.quests.values():
            if q.giver_id and self.engine.npc_manager.get_npc(q.giver_id):
                quest = q
                break
        if quest is None:
            self.skipTest("no NPC-given quest")
        giver = self.engine.npc_manager.get_npc(quest.giver_id)
        before = giver.get_relationship(self.engine.player.id)

        # Force the quest into a turn-in-able state
        from quests.quest import QuestStatus
        quest.status = QuestStatus.COMPLETED
        self.assertTrue(self.engine.turn_in_quest(quest.id))
        after = giver.get_relationship(self.engine.player.id)
        self.assertGreaterEqual(after, before + 15)


if __name__ == "__main__":
    unittest.main()
