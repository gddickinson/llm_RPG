"""Traversal framework tests (P11.1)."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class _FixedRng:
    def __init__(self, value):
        self.value = value

    def randint(self, a, b):
        return self.value


class TestTraversal(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.player = self.engine.player
        self.trav = self.engine.traversal
        # staging corner: a lake with a deep middle
        self.ox, self.oy = self.wmap.width - 12, self.wmap.height - 10
        for y in range(self.oy - 4, self.oy + 6):
            for x in range(self.ox - 4, self.ox + 8):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put_player(self, x, y):
        self.wmap.remove_character(self.player)
        self.player.position = (x, y)
        self.wmap.place_character(self.player, x, y)

    def _lake(self):
        """A 3x3 lake east of the player: the middle tile is deep."""
        for dy in (-1, 0, 1):
            for dx in (0, 1, 2):
                self.wmap.terrain[self.oy + dy][self.ox + 1 + dx] = \
                    TerrainType.WATER
        return self.ox + 2, self.oy    # the deep column

    def test_shore_is_shallow_deep_is_not(self):
        self._lake()
        self.assertTrue(self.trav.is_shallow(self.ox + 1, self.oy))
        self.assertFalse(self.trav.is_shallow(self.ox + 2, self.oy),
                         "all-water neighbors = deep")

    def test_wading_tires_but_never_fails(self):
        self._lake()
        self._put_player(self.ox, self.oy)
        self.trav.rng = _FixedRng(1)
        fatigue0 = self.player.metadata.get("fatigue", 10)
        self.assertTrue(self.engine.player_actions.move(1, 0))
        self.assertEqual(self.player.position, (self.ox + 1, self.oy))
        self.assertGreater(self.player.metadata["fatigue"], fatigue0)

    def test_deep_water_takes_a_swim_check(self):
        self._lake()
        self._put_player(self.ox + 1, self.oy)     # standing in shallows
        self.trav.rng = _FixedRng(1)               # doomed
        self.assertFalse(self.engine.player_actions.move(1, 0))
        self.assertEqual(self.player.position, (self.ox + 1, self.oy))
        self.trav.rng = _FixedRng(20)              # heroic
        xp0 = self.player.metadata.get("skills", {}).get("swimming", 0)
        self.assertTrue(self.engine.player_actions.move(1, 0))
        self.assertEqual(self.player.position, (self.ox + 2, self.oy))
        xp1 = self.player.metadata.get("skills", {}).get("swimming", 0)
        self.assertGreater(xp1, xp0, "swimming trains Swimming")

    def test_bad_fail_hurts_but_never_kills(self):
        self._lake()
        self._put_player(self.ox + 1, self.oy)
        self.player.hp = 1
        self.trav.rng = _FixedRng(1)
        self.assertFalse(self.engine.player_actions.move(1, 0))
        self.assertEqual(self.player.hp, 1,
                         "scrapes maim; the story kills")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("under", log.lower())

    def test_encumbrance_and_exhaustion_raise_the_dc(self):
        rule = self.trav.rules["water"]
        base = self.trav.check_dc(rule)
        from engine.carry import capacity
        self.player.inventory = ["rock"] * capacity(self.player)
        heavy = self.trav.check_dc(rule)
        self.assertGreater(heavy, base, "a full pack drags you down")
        self.player.inventory = []
        self.player.metadata["fatigue"] = 95
        tired = self.trav.check_dc(rule)
        self.assertGreater(tired, base, "exhaustion makes it harder")

    def test_swamp_slog_taxes_the_step(self):
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.SWAMP
        self._put_player(self.ox, self.oy)
        self.player.metadata["fatigue"] = 10
        minutes0 = self.engine.world.time
        self.assertTrue(self.engine.player_actions.move(1, 0))
        self.assertGreater(self.player.metadata["fatigue"], 10)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("bog", log.lower())

    def test_sleep_resets_fatigue(self):
        from engine import rest
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      or "inn" in l.name.lower())
        self._put_player(tavern.x + tavern.width // 2,
                         tavern.y + tavern.height // 2)
        self.player.gold = 100
        self.player.metadata["fatigue"] = 80
        rest.sleep(self.engine)
        self.assertEqual(self.player.metadata.get("fatigue"), 0)

    def test_rules_are_data_and_reference_real_skills(self):
        from engine.skill_progression import SKILLS
        self.assertIn("water", self.trav.rules)
        self.assertIn("mountain", self.trav.rules)
        self.assertIn("swimming", SKILLS,
                      "Swimming joined the lattice")
        for rule in self.trav.rules.values():
            skill = rule.get("skill")
            if skill:
                self.assertIn(skill, SKILLS)


if __name__ == "__main__":
    unittest.main()
