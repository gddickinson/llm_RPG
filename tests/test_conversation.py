"""Conversation menu (PUX.6): a talk surfaces the NPC's quests, trade,
topics and secrets as visible numbered picks — no more guessing 1-9."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine import conversation                      # noqa: E402
from engine.game_engine import GameEngine            # noqa: E402


def _npc_with(engine, kind):
    """First world NPC whose conversation menu offers `kind`."""
    for npc in engine.npc_manager.npcs.values():
        if any(i["kind"] == kind for i in conversation.menu(engine, npc)):
            return npc
    return None


class TestConversationModel(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_merchant_offers_trade_but_a_guard_does_not(self):
        merchant = _npc_with(self.engine, "trade")
        self.assertIsNotNone(merchant, "some merchant sells wares")
        self.assertTrue(conversation.is_merchant(merchant))
        guard = self.engine.npc_manager.get_npc("guard_01")
        if guard is not None:                 # a guard is no shopkeeper
            self.assertFalse(conversation.is_merchant(guard))

    def test_a_quest_giver_offers_accept(self):
        giver = _npc_with(self.engine, "accept")
        self.assertIsNotNone(giver, "someone has a quest to give")
        labels = [i["label"] for i in conversation.menu(self.engine, giver)]
        self.assertTrue(any(l.startswith("Accept:") for l in labels))

    def test_menu_items_are_well_formed(self):
        for npc in self.engine.npc_manager.npcs.values():
            for item in conversation.menu(self.engine, npc):
                self.assertIn("kind", item)
                self.assertIn("label", item)
                self.assertIn(item["kind"], ("accept", "turnin", "trade",
                                             "topic", "secret", "social"))


class TestConversationInGui(unittest.TestCase):
    def _gui(self):
        import pygame
        pygame.display.init()
        pygame.display.set_mode((1280, 800))
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        from ui.gui import GameGUI
        return GameGUI(engine)

    def test_picking_a_quest_accepts_it(self):
        gui = self._gui()
        giver = _npc_with(gui.engine, "accept")
        gui.start_dialog(giver.id)
        self.assertTrue(gui.dialog_menu, "the menu is populated")
        idx = next(i for i, it in enumerate(gui.dialog_menu)
                   if it["kind"] == "accept")
        qid = gui.dialog_menu[idx]["quest_id"]
        gui.dialog_quest_action(idx)
        active = [q.id for q in gui.engine.quest_manager.active()]
        self.assertIn(qid, active, "the picked quest was accepted")
        gui.engine.end_game()

    def test_picking_trade_opens_the_shop(self):
        gui = self._gui()
        merchant = _npc_with(gui.engine, "trade")
        gui.start_dialog(merchant.id)
        idx = next(i for i, it in enumerate(gui.dialog_menu)
                   if it["kind"] == "trade")
        gui.dialog_quest_action(idx)
        self.assertEqual(gui.mode, "shop")
        self.assertIsNotNone(gui.shop_panel)
        gui.engine.end_game()

    def test_dialog_box_draws_with_a_menu(self):
        import pygame
        gui = self._gui()
        giver = _npc_with(gui.engine, "accept")
        gui.start_dialog(giver.id)
        surf = pygame.Surface((1280, 800))
        gui.hud.draw_dialog_box(surf, surf.get_rect(), giver.name,
                                "Hello there.", menu=gui.dialog_menu)
        gui.engine.end_game()


if __name__ == "__main__":
    unittest.main()
