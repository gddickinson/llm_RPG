"""Magical sight through walls (P14.2): a keen_sight effect lets the player
SEE the figures behind walls — sight only, reach still stops at the stone."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from characters.status_effects import VALID_EFFECTS, apply_effect, has_effect
from engine.game_engine import GameEngine
from engine.presence import (hidden_by_walls, is_indoors,
                             npc_adjacent_to_player, sees_through_walls)


class TestKeenSight(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        # an NPC standing inside a building's footprint
        self.indoor = next(
            (n for n in self.engine.npc_manager.npcs.values()
             if n.is_active() and is_indoors(self.engine, n)), None)
        if self.indoor is None:
            loc = next(l for l in self.engine.world.locations
                       if l.name in self.engine.interiors)
            self.indoor = next(iter(self.engine.npc_manager.npcs.values()))
            self.indoor.position = (loc.x, loc.y)
        # stand the player WELL AWAY from the building, so only the
        # magical sight (not a window glimpse) could reveal the figure
        bldg = is_indoors(self.engine, self.indoor)
        loc = next(l for l in self.engine.world.locations
                   if l.name == bldg)
        far_x = loc.x + loc.width + 4
        if far_x >= self.engine.world.map.width - 1:
            far_x = max(1, loc.x - 4)
        self.p.position = (far_x, loc.y)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_keen_sight_is_a_valid_effect(self):
        self.assertIn("keen_sight", VALID_EFFECTS)

    def test_the_indoors_are_hidden_without_it(self):
        self.assertFalse(sees_through_walls(self.engine))
        self.assertTrue(hidden_by_walls(self.engine, self.indoor),
                        "you can't see the merchant behind his wall")

    def test_keen_sight_pierces_the_wall(self):
        apply_effect(self.p, "keen_sight", 20)
        self.assertTrue(sees_through_walls(self.engine))
        self.assertFalse(hidden_by_walls(self.engine, self.indoor),
                         "now you glimpse the figure inside")

    def test_sight_is_not_reach(self):
        apply_effect(self.p, "keen_sight", 20)
        self.assertFalse(npc_adjacent_to_player(self.engine, self.indoor),
                         "you see him, but can't barter through the stone")

    def test_the_player_is_never_hidden_from_themselves(self):
        self.assertFalse(hidden_by_walls(self.engine, self.p))

    def test_the_spell_grants_the_sight(self):
        self.p.metadata.setdefault("spells_known", []).append("keen_sight")
        self.p.metadata["mana"] = 20
        self.p.metadata["max_mana"] = 20
        msg = self.engine.cast_spell("keen_sight", "me")
        self.assertIn("keen_sight", msg)
        self.assertTrue(has_effect(self.p, "keen_sight"))
        self.assertTrue(sees_through_walls(self.engine))


if __name__ == "__main__":
    unittest.main()
