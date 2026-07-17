"""The COLOSSEUM — a combat-testing arena (George)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_NO_ADVENTURERS", "1")
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_col_"))

import unittest

from engine.game_engine import GameEngine
from engine.colosseum import ColosseumSystem, is_fighter


class TestColosseum(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def setUp(self):
        self.col = self.engine.colosseum
        self.col.clear()

    def test_seeded_at_startup(self):
        self.assertIsNotNone(self.col.arena, "the arena seeds at world start")
        self.assertTrue(self.col.matchups(), "matchups load from json")

    def test_stage_spawns_two_teams(self):
        self.assertTrue(self.col.stage("warrior_duel"))
        teams = {(self.engine.npc_manager.npcs[f].metadata.get("arena_team"))
                 for f in self.col.fighter_ids}
        self.assertEqual(teams, {0, 1}, "a fighter on each side")
        for fid in self.col.fighter_ids:
            self.assertTrue(is_fighter(self.engine.npc_manager.npcs[fid]))

    def test_a_duel_resolves_to_a_winner(self):
        self.col.stage("warrior_duel")
        for _ in range(300):
            self.col.run_turn()
            if not self.col.active:
                break
        self.assertFalse(self.col.active, "the fight ends")
        self.assertIn(self.col.result, ("team_a", "team_b", "draw"))

    def test_a_team_battle_resolves(self):
        self.col.stage("melee_vs_ranged")
        for _ in range(400):
            self.col.run_turn()
            if not self.col.active:
                break
        self.assertIsNotNone(self.col.result, "a team battle finishes")

    def test_clear_removes_the_fighters(self):
        self.col.stage("warrior_duel")
        ids = list(self.col.fighter_ids)
        self.col.clear()
        self.assertEqual(self.col.fighter_ids, [])
        for fid in ids:
            self.assertNotIn(fid, self.engine.npc_manager.npcs)

    def test_enter_seats_the_spectator_and_stages(self):
        self.assertTrue(self.engine.enter_colosseum("beast_brawl"))
        self.assertTrue(self.col.active)
        self.assertTrue(self.col.at_entrance(self.engine.player.position))
        self.col.clear()

    def test_arena_persists_the_rect(self):
        d = self.col.to_dict()
        self.col.arena = None
        self.col.from_dict(d)
        self.assertIsNotNone(self.col.arena)

    def test_fighters_skip_the_ambient_ai(self):
        # a staged fighter is ignored by the pursuit eligibility (the arena
        # drives them, not the systems that chase the player)
        self.col.stage("warrior_duel")
        f = self.engine.npc_manager.npcs[self.col.fighter_ids[0]]
        self.assertTrue(is_fighter(f))
        self.assertFalse(self.engine.pursuit._is_pursuer(
            f, set(), self.engine.world.map),
            "the arena fighter is not a pursuer of the spectator")


if __name__ == "__main__":
    unittest.main()
