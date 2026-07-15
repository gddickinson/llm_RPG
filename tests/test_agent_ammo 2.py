"""Agent doesn't dry-fire an empty quiver (bug-fix 2026-07-12).

The autoplay/M.2 agent used to keep 'shooting' a bow with no arrows left,
so a driven hero just stood in place forever. `_can_shoot` now requires
matching ammo (thrown weapons excepted), so an empty-quivered agent closes
to melee and keeps moving."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_ammo_"))

import unittest

from engine.game_engine import GameEngine
from engine.agent_controller import AgentController, _can_shoot
from items.item_registry import create_item
from characters.equipment import equip
from world.monsters import build_monster
from world.world_map import TerrainType


class TestAgentAmmo(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        bow = create_item("bow")
        self.assertIsNotNone(bow, "need a bow item to test")
        equip(self.p, bow)
        self._strip_ammo()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _strip_ammo(self):
        self.p.inventory = [it for it in self.p.inventory
                            if not (hasattr(it, "is_ammo") and it.is_ammo())]

    def test_no_ammo_cannot_shoot(self):
        self.assertFalse(_can_shoot(self.p))

    def test_ammo_can_shoot(self):
        arrows = create_item("arrow")
        self.assertIsNotNone(arrows)
        self.p.inventory.append(arrows)
        self.assertTrue(_can_shoot(self.p))

    def test_empty_quiver_agent_closes_instead_of_firing(self):
        # a plain archer, not a caster — so no M.8c spell intercepts the
        # ammo-behaviour under test (the default class varies by RNG order)
        self.p.metadata["spells_known"] = []
        wmap = self.engine.world.map
        for yy in range(8, 16):
            for xx in range(8, 16):
                wmap.terrain[yy][xx] = TerrainType.GRASS
        wmap.remove_character(self.p)
        self.p.position = (10, 10)
        wmap.place_character(self.p, 10, 10)
        foe = build_monster("wolf", (13, 10))
        self.engine.npc_manager.add_npc(foe)
        wmap.place_character(foe, 13, 10)
        plan = AgentController().decide(self.engine, self.p)
        self.assertEqual(plan[0], "move",
                         "with no arrows it closes to melee, not dry-fires")


if __name__ == "__main__":
    unittest.main()
