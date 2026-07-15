"""Autoplay control (M.3, bug-fix 2026-07-12d).

The away-hero heartbeat drives the hero each tick; a hero-DIRECTING key
(move/act) hands control back, but an OBSERVE key (settings, a journal,
the map) does NOT — so opening the settings overlay to confirm autoplay
no longer silently switches it off ("autoplay doesn't seem to work").
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_auto_"))

import unittest

import pygame

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from ui.away_mode import hands_back, heartbeat, HEARTBEAT_FRAMES


class TestHandBack(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.engine.roster.set_away(self.engine.player, True)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _ev(self, key, kind=pygame.KEYDOWN):
        return pygame.event.Event(kind, key=key)

    def test_observe_keys_keep_autoplay(self):
        # opening settings / a journal / the map must NOT end autoplay
        for k in (pygame.K_COMMA, pygame.K_i, pygame.K_q, pygame.K_o,
                  pygame.K_j, pygame.K_u, pygame.K_y, pygame.K_ESCAPE):
            self.assertFalse(hands_back(self.engine, self._ev(k)),
                             f"{k} should not hand back")

    def test_control_keys_hand_back(self):
        for k in (pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d,
                  pygame.K_SPACE, pygame.K_f, pygame.K_r):
            self.assertTrue(hands_back(self.engine, self._ev(k)),
                            f"{k} should hand back")

    def test_not_away_never_hands_back(self):
        self.engine.roster.set_away(self.engine.player, False)
        self.assertFalse(hands_back(self.engine, self._ev(pygame.K_w)))

    def test_key_release_does_not_hand_back(self):
        self.assertFalse(
            hands_back(self.engine, self._ev(pygame.K_w, pygame.KEYUP)))


class TestHeartbeatDrives(unittest.TestCase):
    """The heartbeat actually advances the world and moves the away hero."""

    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        # open ground, no crowd — so the driven hero explores and moves
        p = self.engine.player
        for yy in range(2, 26):
            for xx in range(2, 26):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        for nid in list(self.engine.npc_manager.npcs):
            n = self.engine.npc_manager.npcs[nid]
            self.engine.world.map.remove_character(n)
            self.engine.npc_manager.remove_npc(nid)
        self.engine.world.map.remove_character(p)
        p.position = (13, 13)
        self.engine.world.map.place_character(p, 13, 13)
        self.engine.roster.set_away(p, True)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_heartbeat_ticks_and_drives(self):
        class _Gui:
            pass
        gui = _Gui()
        gui.engine = self.engine
        pos0 = tuple(self.engine.player.position)
        turn0 = self.engine.turn_counter
        moved = False
        for _ in range(HEARTBEAT_FRAMES * 12):
            heartbeat(gui)
            if tuple(self.engine.player.position) != pos0:
                moved = True                 # a wanderer can loop back to start,
        self.assertGreater(self.engine.turn_counter, turn0)   # world ticked
        self.assertTrue(moved, "the away hero moved at some point")   # so track it

    def test_heartbeat_idle_when_not_away(self):
        self.engine.roster.set_away(self.engine.player, False)

        class _Gui:
            pass
        gui = _Gui()
        gui.engine = self.engine
        turn0 = self.engine.turn_counter
        for _ in range(HEARTBEAT_FRAMES * 4):
            heartbeat(gui)
        self.assertEqual(self.engine.turn_counter, turn0)     # frozen


class TestAutoplaySpeed(unittest.TestCase):
    """M.9b — the watcher can slow/speed/pause/step the autoplay cadence."""

    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.engine.roster.set_away(self.engine.player, True)

        class _Gui:
            pass
        self.gui = _Gui()
        self.gui.engine = self.engine

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_default_speed_is_normal(self):
        from ui.away_mode import speed_label
        self.assertEqual(speed_label(self.gui), "normal")

    def test_speed_clamps_at_both_ends(self):
        from ui.away_mode import cycle_speed, speed_label
        for _ in range(5):
            cycle_speed(self.gui, 1)
        self.assertEqual(speed_label(self.gui), "blitz")
        for _ in range(9):
            cycle_speed(self.gui, -1)
        self.assertEqual(speed_label(self.gui), "paused")

    def test_paused_does_not_tick(self):
        from ui.away_mode import cycle_speed, heartbeat
        for _ in range(9):
            cycle_speed(self.gui, -1)                 # -> paused
        t0 = self.engine.turn_counter
        for _ in range(40):
            heartbeat(self.gui)
        self.assertEqual(self.engine.turn_counter, t0)

    def test_single_step_advances_even_when_paused(self):
        from ui.away_mode import cycle_speed, single_step
        for _ in range(9):
            cycle_speed(self.gui, -1)
        t0 = self.engine.turn_counter
        single_step(self.gui)
        self.assertEqual(self.engine.turn_counter, t0 + 1)

    def test_blitz_ticks_more_than_normal(self):
        from ui.away_mode import heartbeat, cycle_speed
        t0 = self.engine.turn_counter
        for _ in range(30):
            heartbeat(self.gui)                       # normal
        normal = self.engine.turn_counter - t0
        for _ in range(3):
            cycle_speed(self.gui, 1)                  # -> blitz
        t1 = self.engine.turn_counter
        for _ in range(30):
            heartbeat(self.gui)
        self.assertGreater(self.engine.turn_counter - t1, normal)

    def test_cadence_keys_consumed_and_never_hand_back(self):
        from ui.away_mode import handle_speed_key
        for key in (pygame.K_EQUALS, pygame.K_MINUS, pygame.K_PERIOD):
            ev = pygame.event.Event(pygame.KEYDOWN, key=key)
            self.assertTrue(handle_speed_key(self.gui, ev))
            self.assertFalse(hands_back(self.engine, ev))


class TestSpectatorPanel(unittest.TestCase):
    """M.9c — the spectator card tells the story of what the away-hero is up
    to (aim, bearing, standing, band)."""

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

    def test_no_card_while_the_human_plays(self):
        from ui.away_mode import spectator_lines
        self.assertIsNone(spectator_lines(self.engine))

    def test_card_shows_aim_bearing_standing(self):
        from ui.away_mode import spectator_lines
        self.engine.roster.set_away(self.p, True)
        self.p.metadata["agent_goal"] = "Ruined Keep"
        blob = " ".join(spectator_lines(self.engine))
        self.assertIn("Ruined Keep", blob)         # aim
        self.assertIn("Bearing", blob)              # disposition
        self.assertIn("HP", blob)                   # standing
        self.assertIn("g", blob)                    # gold

    def test_band_reports_a_companion(self):
        from ui.away_mode import spectator_lines
        from world.monsters import build_monster
        from characters.character_types import CharacterClass
        self.engine.companion_manager.party = []
        self.engine.roster.set_away(self.p, True)
        ally = build_monster("wolf", (0, 0))
        ally.id, ally.name = "kes", "Kestrel"
        ally.character_class = CharacterClass("ranger")
        self.engine.npc_manager.add_npc(ally)
        self.engine.companion_manager.party.append("kes")
        self.assertIn("Kestrel", " ".join(spectator_lines(self.engine)))

    def test_band_alone_when_partyless(self):
        from ui.away_mode import spectator_lines
        self.engine.companion_manager.party = []
        self.engine.roster.set_away(self.p, True)
        self.assertIn("alone", " ".join(spectator_lines(self.engine)))


if __name__ == "__main__":
    unittest.main()
