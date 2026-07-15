"""M.9d — a high-level AMBITION the player sets for the absence (get rich /
clear the deeps / master the arcane / found a company) biases the away
agent BEYOND the six dispositions: it redraws where the hero roams and
widens the loot/social reach that serves the goal.
"""

import os as _os
import unittest

from engine.game_engine import GameEngine
from engine.agent_controller import AgentController
from engine import agent_goals as agoals
from engine.settings import get_setting, set_setting
from world.world_map import TerrainType
from world.location import Location
from characters.character_types import CharacterClass


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.p.character_class = CharacterClass.WARRIOR
        self.ac = AgentController()
        self.ac.visited = set()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _place(self, name, x, y):
        loc = Location(name=name, description="a place", x=x, y=y,
                       width=1, height=1)
        self.engine.world.locations.append(loc)
        return loc


class TestAmbitionReader(_Base):
    def test_defaults_to_none(self):
        self.assertEqual(agoals.ambition(self.p), "none")

    def test_reads_the_setting(self):
        set_setting(self.p, "ambition", "wealth")
        self.assertEqual(agoals.ambition(self.p), "wealth")

    def test_setting_persists_in_metadata(self):
        set_setting(self.p, "ambition", "delve")
        self.assertEqual(get_setting(self.p, "ambition"), "delve")


class TestAmbitionDraw(_Base):
    """A set ambition OVERRIDES the class calling for where the hero roams."""

    def setUp(self):
        super().setUp()
        # a clean slate of named places to choose between, all equidistant-ish
        self.engine.world.locations = []
        self.p.position = (30, 30)
        self._place("Gloomfang Cave", 32, 30)      # delve
        self._place("Copper Market", 30, 32)       # wealth
        self._place("Adept's Tower", 28, 30)       # mastery
        self._place("The Wayfarer Tavern", 30, 28)  # fellowship

    def _goal_for(self, amb):
        set_setting(self.p, "ambition", amb)
        self.ac.visited = set()
        self.ac.goal_name = None
        agoals.named_goal(self.ac, self.engine, self.p)
        return self.ac.goal_name

    def test_wealth_draws_to_the_market(self):
        self.assertEqual(self._goal_for("wealth"), "Copper Market")

    def test_delve_draws_to_the_cave(self):
        self.assertEqual(self._goal_for("delve"), "Gloomfang Cave")

    def test_mastery_draws_to_the_tower(self):
        self.assertEqual(self._goal_for("mastery"), "Adept's Tower")

    def test_fellowship_draws_to_the_tavern(self):
        self.assertEqual(self._goal_for("fellowship"), "The Wayfarer Tavern")

    def test_none_falls_back_to_the_class_calling(self):
        # a warrior with no ambition is drawn to the cave (its CLASS_DRAW),
        # not the market/tower/tavern
        self.assertEqual(self._goal_for("none"), "Gloomfang Cave")


class TestAmbitionBehaviour(_Base):
    """Wealth widens the loot reach (like greedy); fellowship widens the
    social reach (like sociable) — beyond whatever disposition is set."""

    def setUp(self):
        super().setUp()
        for yy in range(2, 30):
            for xx in range(2, 30):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        for nid in list(self.engine.npc_manager.npcs):
            n = self.engine.npc_manager.npcs[nid]
            self.engine.world.map.remove_character(n)
            self.engine.npc_manager.remove_npc(nid)
        self.engine.world.map.remove_character(self.p)
        self.p.position = (10, 10)
        self.engine.world.map.place_character(self.p, 10, 10)
        self.engine.roster.set_away(self.p, True)
        set_setting(self.p, "disposition", "balanced")

    def _drop_loot(self, x, y):
        from items.item_registry import create_item
        itm = create_item("leather")
        self.engine.world.add_item_to_ground(itm, x, y)
        return itm

    def test_wealth_widens_the_loot_reach(self):
        # a sword 7 tiles off — outside the default r=5, inside greedy's r=8
        self._drop_loot(17, 10)
        self.assertIsNone(self.ac._nearest_loot(self.engine, self.p, r=5))
        self.assertEqual(self.ac._nearest_loot(self.engine, self.p, r=8),
                         (17, 10))

    def test_wealth_hero_steps_toward_distant_loot(self):
        self._drop_loot(17, 10)
        set_setting(self.p, "ambition", "wealth")
        kind, *rest = self.ac.decide(self.engine, self.p)
        self.assertEqual(kind, "move")
        self.assertGreater(rest[0][0], 0)  # stepping east, toward the loot

    def test_no_wealth_leaves_distant_loot_out_of_reach(self):
        # without the wealth ambition the same distant loot isn't sought
        self._drop_loot(17, 10)
        set_setting(self.p, "ambition", "none")
        self.assertIsNone(self.ac._nearest_loot(self.engine, self.p, r=5))


class TestSpectatorShowsAmbition(_Base):
    def test_ambition_appears_on_the_card(self):
        from ui.away_mode import spectator_lines
        self.engine.roster.set_away(self.p, True)
        set_setting(self.p, "ambition", "delve")
        lines = spectator_lines(self.engine) or []
        self.assertTrue(any("delve" in ln for ln in lines),
                        "the spectator card should name the ambition")

    def test_no_ambition_line_when_none(self):
        from ui.away_mode import spectator_lines
        self.engine.roster.set_away(self.p, True)
        set_setting(self.p, "ambition", "none")
        lines = spectator_lines(self.engine) or []
        self.assertFalse(any("Ambition" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
