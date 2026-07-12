"""Absent-player persistence (M.3): when a human steps away, the agent
keeps their hero living; any return hands control back."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine            # noqa: E402
from engine.agent_controller import AgentController, drive_agents  # noqa: E402
from world.monsters import build_monster             # noqa: E402


class TestAwayFlag(unittest.TestCase):
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

    def test_set_away_captures_home_and_lists(self):
        r = self.engine.roster
        self.assertFalse(r.is_away(self.p))
        r.set_away(self.p, True)
        self.assertTrue(r.is_away(self.p))
        self.assertEqual(r.controller_for(self.p).away_home,
                         tuple(self.p.position))
        self.assertIn(self.p, r.away_characters())
        r.set_away(self.p, False)
        self.assertFalse(r.is_away(self.p))
        self.assertEqual(r.away_characters(), [])

    def test_away_hero_is_driven_and_defends(self):
        r = self.engine.roster
        r.set_away(self.p, True)
        px, py = self.p.position
        wolf = build_monster("wolf", (px + 1, py))
        self.engine.npc_manager.add_npc(wolf)
        hp0 = wolf.hp
        self.engine._advancing = True         # as if inside a world turn
        try:
            # a d20 swing can miss; a few drives lands one
            for _ in range(12):
                if wolf.hp < hp0:
                    break
                drive_agents(self.engine)     # the agent takes the hero
            self.assertLess(wolf.hp, hp0, "the away hero defended itself")
        finally:
            self.engine._advancing = False

    def test_hand_back_stops_the_agent(self):
        r = self.engine.roster
        px, py = self.p.position
        wolf = build_monster("wolf", (px + 1, py))
        self.engine.npc_manager.add_npc(wolf)
        r.set_away(self.p, False)             # human is at the controls
        hp0 = wolf.hp
        self.engine._advancing = True
        try:
            drive_agents(self.engine)
            self.assertEqual(wolf.hp, hp0, "the human's hero isn't driven")
        finally:
            self.engine._advancing = False

    def test_away_hero_potters_toward_home(self):
        ctrl = AgentController(seed=1)
        ctrl.home = (self.p.position[0] + 4, self.p.position[1])
        self.assertEqual(ctrl._pick_goal(self.engine, self.p), ctrl.home)

    def test_idle_away_hero_strikes_out_to_explore(self):
        # with no home to hug (or standing on it), it roams within ROAM
        ctrl = AgentController(seed=3)
        ctrl.home = None
        x, y = self.p.position
        for _ in range(20):
            gx, gy = ctrl._pick_goal(self.engine, self.p)
            self.assertLessEqual(abs(gx - x), ctrl.ROAM)
            self.assertLessEqual(abs(gy - y), ctrl.ROAM)

    def test_set_away_keeps_the_autoplay_setting_honest(self):
        from engine import settings
        r = self.engine.roster
        r.set_away(self.p, True)
        self.assertEqual(settings.get_setting(self.p, "autoplay"), "on")
        # a keypress hands control back -> the toggle must read off too
        r.set_away(self.p, False)
        self.assertEqual(settings.get_setting(self.p, "autoplay"), "off")

    def test_autoplay_banner_only_while_away(self):
        from ui.away_mode import banner_text, BANNER
        r = self.engine.roster
        self.assertIsNone(banner_text(self.engine))    # human at controls
        r.set_away(self.p, True)
        self.assertEqual(banner_text(self.engine), BANNER)
        r.set_away(self.p, False)
        self.assertIsNone(banner_text(self.engine))


class TestHeartbeat(unittest.TestCase):
    def test_world_ticks_only_while_away(self):
        import pygame
        pygame.display.init()
        pygame.display.set_mode((1280, 800))
        from ui.gui import GameGUI
        from ui.away_mode import heartbeat, HEARTBEAT_FRAMES
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        gui = GameGUI(engine)
        tc0 = engine.turn_counter
        for _ in range(HEARTBEAT_FRAMES + 2):     # not away -> frozen
            heartbeat(gui)
        self.assertEqual(engine.turn_counter, tc0)
        engine.roster.set_away(engine.player, True)
        for _ in range(HEARTBEAT_FRAMES):         # away -> one tick
            heartbeat(gui)
        self.assertEqual(engine.turn_counter, tc0 + 1)
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
