"""T4.1 away-hero building entry: a loop-proof enter -> act -> exit that
lights up inn-rest + indoor-merchant trade for the driven active hero."""

import unittest

from engine.game_engine import GameEngine
from engine import agent_building as abld
from engine.agent_controller import AgentController


class _Ctrl:
    """A minimal stand-in for the AgentController state agent_building uses."""
    def __init__(self, social=True):
        self.social = social
        self.indoor = None
        self._indoor_cd = 0
        self.visited = set()


class TestEnterIntent(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.inn = self._find(("inn", "tavern"))

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _find(self, kinds):
        for loc in self.engine.world.locations:
            if loc.name in self.engine.interiors and abld._matches(loc, kinds):
                return loc
        return None

    def _stand_beside(self, loc):
        # a walkable overworld tile within 2 of the footprint
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        for r in range(1, 3):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    x, y = loc.x + dx, loc.y + dy
                    if (0 <= x < wmap.width and 0 <= y < wmap.height
                            and wmap.terrain[y][x] not in (
                                TerrainType.BUILDING, TerrainType.WATER,
                                TerrainType.MOUNTAIN)):
                        self.p.position = (x, y)
                        return True
        return False

    def test_hurt_beside_inn_enters_to_rest(self):
        if self.inn is None or not self._stand_beside(self.inn):
            self.skipTest("no reachable inn in this world")
        self.p.hp = 1
        self.p.max_hp = 30
        self.p.gold = 50
        ctrl = _Ctrl(social=True)
        intent = abld.enter_intent(ctrl, self.engine, self.p)
        self.assertIsNotNone(intent)
        self.assertEqual(intent[1], "rest")

    def test_healthy_hero_does_not_enter(self):
        if self.inn is None or not self._stand_beside(self.inn):
            self.skipTest("no reachable inn")
        self.p.hp = self.p.max_hp
        ctrl = _Ctrl(social=True)
        self.assertIsNone(abld.enter_intent(ctrl, self.engine, self.p))

    def test_adventurer_npc_never_enters(self):
        if self.inn is None or not self._stand_beside(self.inn):
            self.skipTest("no reachable inn")
        self.p.hp = 1
        self.p.gold = 50
        ctrl = _Ctrl(social=False)          # a background adventurer
        self.assertIsNone(abld.enter_intent(ctrl, self.engine, self.p))

    def test_cooldown_blocks_entry(self):
        if self.inn is None or not self._stand_beside(self.inn):
            self.skipTest("no reachable inn")
        self.p.hp = 1
        self.p.gold = 50
        ctrl = _Ctrl(social=True)
        ctrl._indoor_cd = 10
        self.assertIsNone(abld.enter_intent(ctrl, self.engine, self.p))


class TestStateMachine(unittest.TestCase):
    def test_act_then_leave_sets_cooldown_and_visited(self):
        ctrl = _Ctrl()
        abld.on_entered(ctrl, None, _Loc("The Prancing Pony"), "rest")
        self.assertEqual(ctrl.indoor["task"], "rest")
        # first inside tick: do the task
        # (engine unused for a rest task, so None is fine)
        plan = abld.inside_plan(ctrl, None, None)
        self.assertEqual(plan, ("rest",))
        self.assertTrue(ctrl.indoor["acted"])
        # second inside tick: leave, mark visited, arm the cooldown
        plan2 = abld.inside_plan(ctrl, None, None)
        self.assertEqual(plan2, ("exit_building",))
        self.assertIsNone(ctrl.indoor)
        self.assertIn("The Prancing Pony", ctrl.visited)
        self.assertEqual(ctrl._indoor_cd, abld.INDOOR_COOLDOWN)

    def test_cooldown_ticks_down(self):
        ctrl = _Ctrl()
        ctrl._indoor_cd = 3
        for _ in range(3):
            abld.tick_cooldown(ctrl)
        self.assertEqual(ctrl._indoor_cd, 0)
        abld.tick_cooldown(ctrl)             # never negative
        self.assertEqual(ctrl._indoor_cd, 0)

    def test_entry_failed_arms_cooldown(self):
        ctrl = _Ctrl()
        ctrl.indoor = {"loc": "x", "task": "rest", "acted": False}
        abld.on_entry_failed(ctrl)
        self.assertIsNone(ctrl.indoor)
        self.assertGreater(ctrl._indoor_cd, 0)


class _Loc:
    def __init__(self, name):
        self.name = name


class TestFullCycleNoLoop(unittest.TestCase):
    def test_enter_rest_exit_then_cooldown_prevents_reentry(self):
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        inn = None
        for loc in engine.world.locations:
            if loc.name in engine.interiors and abld._matches(
                    loc, ("inn", "tavern")):
                inn = loc
                break
        if inn is None:
            engine.end_game()
            self.skipTest("no inn")
        p = engine.player
        ctrl = AgentController(seed=1)
        # 1. enter
        abld.on_entered(ctrl, engine, inn, "rest")
        engine.enter_building(inn)
        self.assertIsNotNone(engine.current_interior)
        # 2. act (rest), 3. leave
        self.assertEqual(abld.inside_plan(ctrl, engine, p), ("rest",))
        self.assertEqual(abld.inside_plan(ctrl, engine, p), ("exit_building",))
        engine.exit_building()
        # 4. back outside, cooldown blocks a re-entry
        self.assertGreater(ctrl._indoor_cd, 0)
        p.hp = 1
        p.gold = 50
        self.assertIsNone(abld.enter_intent(ctrl, engine, p))
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
