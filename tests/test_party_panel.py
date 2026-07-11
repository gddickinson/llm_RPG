"""Party panel (PUX.4b): the companions panel reclaims the old
bottom-right dead zone and shows each ally's order + health."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import pygame                                        # noqa: E402

from engine.game_engine import GameEngine           # noqa: E402


class TestPartyLayout(unittest.TestCase):
    def setUp(self):
        pygame.display.init()
        pygame.display.set_mode((1280, 800))
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        from ui.gui import GameGUI
        self.gui = GameGUI(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_party_region_fills_the_dead_zone(self):
        lay = self.gui.layout
        self.assertIn("party", lay)
        party = lay["party"]
        # bottom-right: right of the map column, below the Quests panel
        self.assertEqual(party.x, self.gui.width - 320)
        self.assertEqual(party.y, self.gui.height - 200)
        self.assertEqual((party.width, party.height), (320, 200))
        # it does not overlap the event log or the mini-map
        for other in ("events", "minimap", "map"):
            self.assertFalse(party.colliderect(lay[other]),
                             f"party overlaps {other}")

    def test_panel_draws_with_no_companions(self):
        surf = pygame.Surface((1280, 800))
        self.gui.hud.draw_party_panel(
            surf, self.engine, self.gui.layout["party"])   # no crash

    def test_panel_shows_a_recruited_companion(self):
        cm = self.engine.companion_manager
        ally_id = next(iter(self.engine.npc_manager.npcs))
        cm.party.append(ally_id)
        ally = self.engine.npc_manager.get_npc(ally_id)
        ally.metadata["order"] = "hold"
        self.assertIn(ally, cm.members())
        surf = pygame.Surface((1280, 800))
        self.gui.hud.draw_party_panel(
            surf, self.engine, self.gui.layout["party"])   # no crash


if __name__ == "__main__":
    unittest.main()
