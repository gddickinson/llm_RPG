"""Player roster & controllers (M.1) — the multiplayer keystone: a
roster of controllable characters, each with a controller, one active.
"""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine            # noqa: E402
from engine.player_roster import (AGENT, HUMAN,       # noqa: E402
                                  PlayerController)
from characters.npc_presets import make_npc          # noqa: E402


class TestController(unittest.TestCase):
    def test_kind_and_round_trip(self):
        h = PlayerController(HUMAN, "George")
        a = PlayerController(AGENT, "Claude")
        self.assertTrue(h.is_human and not h.is_agent)
        self.assertTrue(a.is_agent and not a.is_human)
        self.assertEqual(PlayerController.from_dict(a.to_dict()).kind, AGENT)


class TestRoster(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_seeds_the_active_player_as_human(self):
        r = self.engine.roster
        self.assertIs(r.active, self.engine.player)
        self.assertIn(self.engine.player, r.characters)
        self.assertTrue(r.controller_for(self.engine.player).is_human)
        self.assertEqual(self.engine.player.metadata.get("controller"),
                         HUMAN)

    def test_add_an_agent_character(self):
        r = self.engine.roster
        hero2 = make_npc("guard_01")
        r.add(hero2, PlayerController(AGENT, "Claude"))
        self.assertIn(hero2, r.characters)
        self.assertTrue(r.controller_for(hero2).is_agent)
        self.assertEqual(hero2.metadata["controller"], AGENT)
        self.assertEqual([c.id for c in r.humans()],
                         [self.engine.player.id])
        self.assertEqual([c.id for c in r.agents()], [hero2.id])

    def test_switch_the_active_character(self):
        r = self.engine.roster
        first = self.engine.player
        hero2 = make_npc("guard_01")
        r.add(hero2)
        r.set_active(hero2)
        self.assertIs(self.engine.player, hero2)
        self.assertIs(r.active, hero2)
        r.set_active(first)
        self.assertIs(self.engine.player, first)

    def test_set_active_rejects_a_stranger(self):
        outsider = make_npc("guard_01")
        with self.assertRaises(KeyError):
            self.engine.roster.set_active(outsider)

    def test_survives_a_player_rebuild(self):
        # a load rebuilds engine.player as a NEW object with the same id
        r = self.engine.roster
        _ = r.characters                      # seed it
        old = self.engine.player
        rebuilt = make_npc("guard_01")
        rebuilt.id = old.id                   # same identity, new object
        rebuilt.metadata["controller"] = HUMAN
        self.engine.player = rebuilt          # as SaveManager.load does
        self.assertIn(rebuilt, r.characters)
        self.assertNotIn(old, r.characters)   # stale object dropped
        self.assertTrue(r.controller_for(rebuilt).is_human)


if __name__ == "__main__":
    unittest.main()
