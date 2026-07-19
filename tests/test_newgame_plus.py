"""T4.3 endgame payoff + New Game+: a win pops the victory screen; NG+
carries the hero's legend (level/gear/gold/spells) into a fiercer world."""

import unittest

import pygame

from engine.game_engine import GameEngine
from engine import newgame_plus as ngp
from items.item_registry import create_item


class TestCarryOver(unittest.TestCase):
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

    def test_capture_snapshots_power(self):
        self.p.level = 12
        self.p.gold = 999
        self.p.metadata["spells_known"] = ["fireball", "heal"]
        sword = create_item("sword")
        self.p.inventory.append(sword)
        pay = ngp.capture(self.engine)
        self.assertEqual(pay["ng_plus"], 1)
        self.assertEqual(pay["level"], 12)
        self.assertEqual(pay["gold"], 999)
        self.assertIn("fireball", pay["spells_known"])
        self.assertTrue(pay["inventory"])

    def test_apply_reclothes_a_fresh_hero(self):
        self.p.level = 9
        self.p.gold = 500
        self.p.metadata["ng_plus"] = 2
        self.p.metadata["spells_known"] = ["ice_shard"]
        self.p.inventory.append(create_item("chainmail"))
        pay = ngp.capture(self.engine)
        # a fresh engine (a new world)
        eng2 = GameEngine(llm_provider="heuristic",
                          enable_npc_processes=False)
        eng2.start_game()
        ngp.apply(eng2, pay)
        self.assertEqual(eng2.player.level, 9)
        self.assertEqual(eng2.player.gold, 500)
        self.assertEqual(eng2.player.metadata["ng_plus"], 3)   # incremented
        self.assertIn("ice_shard", eng2.player.metadata["spells_known"])
        self.assertTrue(any(getattr(i, "id", "") == "chainmail"
                            for i in eng2.player.inventory))
        try:
            eng2.end_game()
        except Exception:
            pass

    def test_danger_scales_with_ng_plus(self):
        base = ngp.danger_scale(self.engine)
        self.assertEqual(base, 1.0)
        self.p.metadata["ng_plus"] = 2
        self.assertGreater(ngp.danger_scale(self.engine), 1.0)


class TestVictoryFlow(unittest.TestCase):
    def _gui(self):
        pygame.display.init()
        pygame.display.set_mode((1100, 760))
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        return GameGUI(engine)

    def _key(self, code):
        return pygame.event.Event(pygame.KEYDOWN, key=code, unicode="", mod=0)

    def test_victory_draws_headless(self):
        gui = self._gui()
        gui.engine.player.metadata.setdefault("quest_flags",
                                              {})["campaign_won"] = True
        gui.mode = "victory"
        from ui.victory_screen import draw_victory
        draw_victory(gui)                    # must not raise
        gui.engine.end_game()

    def test_new_game_plus_from_victory(self):
        gui = self._gui()
        p = gui.engine.player
        p.level = 15
        p.gold = 300
        p.metadata.setdefault("quest_flags", {})["campaign_won"] = True
        gui.mode = "victory"
        gui.input_handler.handle_event(self._key(pygame.K_n))
        self.assertEqual(gui.mode, "play")
        # the new world's hero carries the legend + is in NG+
        self.assertEqual(gui.engine.player.level, 15)
        self.assertEqual(gui.engine.player.metadata.get("ng_plus"), 1)
        gui.engine.end_game()

    def test_continue_keeps_playing(self):
        gui = self._gui()
        gui.engine.player.metadata.setdefault("quest_flags",
                                              {})["campaign_won"] = True
        gui.mode = "victory"
        gui.input_handler.handle_event(self._key(pygame.K_c))
        self.assertEqual(gui.mode, "play")
        gui.engine.end_game()


if __name__ == "__main__":
    unittest.main()
