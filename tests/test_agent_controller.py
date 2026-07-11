"""Agent-driven characters (M.2): an autonomous controller plays a
hero through the real player-action route — fights adjacent foes, hunts
nearby ones, wanders otherwise — without cascading extra world ticks.
"""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine            # noqa: E402
from engine.player_roster import AGENT, PlayerController  # noqa: E402
from engine.agent_controller import (AgentController,  # noqa: E402
                                     _dist, _toward, drive_agents)
from world.monsters import build_monster             # noqa: E402
from characters.npc_presets import make_npc          # noqa: E402


class TestHelpers(unittest.TestCase):
    def test_toward(self):
        self.assertEqual(_toward((5, 5), (9, 5)), (1, 0))
        self.assertEqual(_toward((5, 5), (5, 1)), (0, -1))
        self.assertEqual(_toward((5, 5), (5, 5)), (0, 0))


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.hero = make_npc("guard_01")
        self.hero.id = "hero2"
        self.hx, self.hy = self.engine.player.position
        self.hero.position = (self.hx, self.hy)
        self.engine.roster.add(self.hero, PlayerController(AGENT, "Claude"))
        self.ctrl = AgentController(seed=1)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _wolf_at(self, off):
        w = build_monster("wolf", (self.hx + off[0], self.hy + off[1]))
        self.engine.npc_manager.add_npc(w)
        return w

    def test_attacks_an_adjacent_foe(self):
        wolf = self._wolf_at((1, 0))
        plan = self.ctrl.decide(self.engine, self.hero)
        self.assertEqual(plan[0], "attack")
        self.assertIs(plan[1], wolf)

    def test_hunts_a_foe_within_sight(self):
        self._wolf_at((4, 0))                 # 4 east, in sight, not adjacent
        plan = self.ctrl.decide(self.engine, self.hero)
        self.assertEqual(plan, ("move", (1, 0)))   # steps east toward it

    def test_wanders_with_no_foe_in_sight(self):
        # no hostile within SIGHT -> a move/wait toward a cached goal
        plan = self.ctrl.decide(self.engine, self.hero)
        self.assertIn(plan[0], ("move", "wait"))
        self.assertIsNotNone(self.ctrl.goal)

    def test_take_turn_attacks_and_wounds(self):
        wolf = self._wolf_at((1, 0))
        hp0 = wolf.hp
        self.engine._advancing = True         # as if inside a world turn
        try:
            # the decision is deterministic; a single d20 swing may miss,
            # so take a few — at least one lands.
            for _ in range(12):
                if not wolf.is_active():
                    break
                self.assertEqual(
                    self.ctrl.take_turn(self.engine, self.hero), "attack")
            self.assertLess(wolf.hp, hp0, "the agent wounds its foe")
        finally:
            self.engine._advancing = False
        self.assertIsNotNone(self.engine.player)     # player restored


class TestIntegration(unittest.TestCase):
    def test_drive_agents_runs_once_per_turn(self):
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        hero = make_npc("guard_01")
        hero.id = "hero2"
        hx, hy = engine.player.position
        hero.position = (hx + 3, hy)
        engine.roster.add(hero, PlayerController(AGENT, "Claude"))
        active = engine.player
        tc0 = engine.turn_counter
        engine.advance_turn()                 # one world tick
        self.assertEqual(engine.turn_counter - tc0, 1,
                         "the agent's move didn't cascade a second tick")
        self.assertIs(engine.player, active, "the active player is restored")
        self.assertIn("hero2", engine.npc_manager.npcs, "the hero lives on")
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
