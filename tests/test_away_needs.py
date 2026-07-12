"""M.10a — a driven hero tends its NEEDS.

The away hero accrues thirst / hunger / fatigue; the agent must act on a
need before it's dire — drink (a carried drink, or step to the river and
drink), eat, and camp when tired — so it never dies of thirst untried.
"""

import os as _os
import unittest

from engine.game_engine import GameEngine
from engine.agent_controller import AgentController
from engine import agent_exec
from world.world_map import TerrainType
from items.item_registry import create_item


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.ac = AgentController()
        for yy in range(2, 22):
            for xx in range(2, 22):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        self._put(self.p, 10, 10)
        for nid in list(self.engine.npc_manager.npcs):
            n = self.engine.npc_manager.npcs[nid]
            self.engine.world.map.remove_character(n)
            self.engine.npc_manager.remove_npc(nid)
        # start slaked & fed so a test opts INTO a need
        self.p.metadata.update(thirst=10, hunger=10, fatigue=10)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put(self, ch, x, y):
        self.engine.world.map.remove_character(ch)
        ch.position = (x, y)
        self.engine.world.map.place_character(ch, x, y)

    def _give(self, item_id, n=1):
        it = create_item(item_id)
        it.quantity = n
        self.p.inventory.append(it)
        return it


class TestThirst(_Base):
    def test_drinks_a_carried_drink_when_thirsty(self):
        self._give("waterskin")
        self.p.metadata["thirst"] = 80
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "drink")
        self.assertIsNotNone(plan[1])
        self.assertEqual(plan[1].id, "waterskin")

    def test_drinks_from_adjacent_water(self):
        self.p.metadata["thirst"] = 80
        self.engine.world.map.terrain[10][11] = TerrainType.WATER
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan, ("drink", None))

    def test_steps_toward_water_when_thirsty(self):
        self.p.metadata["thirst"] = 80
        # a river tile a few steps east, none adjacent
        self.engine.world.map.terrain[10][14] = TerrainType.WATER
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "move")
        self.assertGreater(plan[1][0], 0)          # heading east, toward it

    def test_not_thirsty_does_not_drink(self):
        self._give("waterskin")
        self.p.metadata["thirst"] = 10
        plan = self.ac.decide(self.engine, self.p)
        self.assertNotEqual(plan[0], "drink")

    def test_a_foe_comes_before_thirst(self):
        from world.monsters import build_monster
        self.p.metadata["thirst"] = 90
        self._give("waterskin")
        foe = build_monster("goblin", (11, 10))
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.place_character(foe, 11, 10)
        plan = self.ac.decide(self.engine, self.p)
        self.assertIn(plan[0], ("attack", "shoot", "cast", "flee", "move"))
        self.assertNotEqual(plan[0], "drink")


class TestHunger(_Base):
    def test_eats_when_hungry(self):
        self._give("bread")
        self.p.metadata["hunger"] = 80
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "eat")
        self.assertEqual(plan[1].id, "bread")

    def test_no_food_no_eat(self):
        self.p.metadata["hunger"] = 80
        plan = self.ac.decide(self.engine, self.p)
        self.assertNotEqual(plan[0], "eat")


class TestTired(_Base):
    def test_camps_when_tired_and_provisioned(self):
        self._give("bread", n=5)                   # provisioned for a real camp
        self.p.metadata.update(fatigue=90, thirst=10, hunger=10)
        self.p.hp = self.p.max_hp                   # not wounded, just tired
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "rest")

    def test_tired_but_unprovisioned_does_not_loop_a_doze(self):
        self.p.metadata.update(fatigue=90, thirst=10, hunger=10)
        self.p.hp = self.p.max_hp
        plan = self.ac.decide(self.engine, self.p)
        self.assertNotEqual(plan[0], "rest")


class TestExecution(_Base):
    def test_drinking_a_waterskin_slakes_thirst(self):
        self._give("waterskin")
        self.p.metadata["thirst"] = 80
        before = self.p.metadata["thirst"]
        agent_exec.execute(self.ac, self.engine, self.p,
                           ("drink", self.p.inventory[-1]))
        self.assertLess(self.p.metadata["thirst"], before)

    def test_drinking_from_the_river_slakes_thirst(self):
        self.p.metadata["thirst"] = 80
        agent_exec.execute(self.ac, self.engine, self.p, ("drink", None))
        self.assertLess(self.p.metadata["thirst"], 80)

    def test_eating_quiets_hunger(self):
        self._give("meat_pie")
        self.p.metadata["hunger"] = 80
        before = self.p.metadata["hunger"]
        agent_exec.execute(self.ac, self.engine, self.p,
                           ("eat", self.p.inventory[-1]))
        self.assertLess(self.p.metadata["hunger"], before)


if __name__ == "__main__":
    unittest.main()
