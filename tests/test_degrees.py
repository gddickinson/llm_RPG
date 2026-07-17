"""Degrees of success tests (P12.1): jackpots and fumbles everywhere."""

import unittest

from engine.game_engine import GameEngine
from engine.skills import Degree, Skill, check, degree_of
from items.item_registry import create_item
from world.world_map import TerrainType


class _FixedRng:
    def __init__(self, value):
        self.value = value

    def randint(self, a, b):
        return self.value

    def random(self):
        return 0.5

    def uniform(self, a, b):
        return (a + b) / 2


class _SeqRng:
    def __init__(self, values):
        self.values = list(values)

    def randint(self, a, b):
        return self.values.pop(0)


class TestDegreeMath(unittest.TestCase):
    def test_margins_grade_the_roll(self):
        self.assertIs(degree_of(25, 15, 10), Degree.CRIT_SUCCESS)
        self.assertIs(degree_of(15, 15, 10), Degree.SUCCESS)
        self.assertIs(degree_of(14, 15, 10), Degree.FAIL)
        self.assertIs(degree_of(5, 15, 10), Degree.CRIT_FAIL)

    def test_natural_rolls_shift_one_degree(self):
        self.assertIs(degree_of(14, 15, 20), Degree.SUCCESS,
                      "nat 20 lifts a miss into a hit")
        self.assertIs(degree_of(16, 15, 1), Degree.FAIL,
                      "nat 1 drags a hit into a miss")
        self.assertIs(degree_of(30, 15, 20), Degree.CRIT_SUCCESS,
                      "no fifth degree above critical")
        self.assertIs(degree_of(1, 15, 1), Degree.CRIT_FAIL)

    def test_check_returns_a_graded_result(self):
        class Dummy:
            dexterity = 14
            level = 1
            name = "Dummy"
        r = check(Dummy(), Skill.LOCKPICKING, dc=10,
                  rng=_FixedRng(20))
        self.assertIs(r.degree, Degree.CRIT_SUCCESS)
        self.assertTrue(r.success and r.crit)


class TestDegreesInSystems(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 12, self.wmap.height - 10
        for y in range(self.oy - 3, self.oy + 4):
            for x in range(self.ox - 3, self.ox + 6):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _locked_door(self):
        name = next(n for n in self.engine.interiors)
        door = self.engine.door_manager.door(name)
        door["state"] = "locked"
        door["lock_level"] = 12
        door.pop("key", None)
        return name

    def test_crit_lockpick_is_flawless(self):
        name = self._locked_door()
        self.player.inventory.append(create_item("lockpicks"))
        self.player.dexterity = 10
        self.engine.door_manager.rng = _FixedRng(20)
        allowed, note = self.engine.door_manager.try_enter(name)
        self.assertTrue(allowed)
        self.assertIn("flawless", note.lower())

    def test_crit_force_fail_pops_the_shoulder(self):
        name = self._locked_door()
        self.player.strength = 10
        self.player.hp = self.player.max_hp
        self.engine.door_manager.rng = _FixedRng(1)
        broke, msg = self.engine.door_manager.force(name)
        self.assertFalse(broke)
        self.assertIn("pops in your shoulder", msg)
        self.assertEqual(self.player.hp, self.player.max_hp - 2)

    def test_crit_force_success_takes_the_hinges(self):
        name = self._locked_door()
        self.player.strength = 18
        self.engine.door_manager.rng = _FixedRng(20)
        broke, msg = self.engine.door_manager.force(name)
        self.assertTrue(broke)
        self.assertIn("hinges", msg)

    def _npc(self):
        return next(n for n in self.engine.npc_manager.npcs.values()
                    if n.is_active())

    def test_crit_persuasion_fail_offends(self):
        npc = self._npc()
        self.engine.persuasion.rng = _FixedRng(1)
        msg = self.engine.persuasion.attempt(npc, "persuade", "please")
        self.assertIn("OFFENDED", msg)

    def test_crit_persuasion_success_is_a_masterstroke(self):
        npc = self._npc()
        rel0 = npc.get_relationship(self.player.id)
        self.engine.persuasion.rng = _FixedRng(20)
        msg = self.engine.persuasion.attempt(npc, "persuade", "friend")
        self.assertIn("masterstroke", msg.lower())
        self.assertGreaterEqual(
            npc.get_relationship(self.player.id) - rel0, 16,
            "a critical success moves them double")

    def test_crit_shove_hurls_two_tiles(self):
        from engine.tactics import shove
        from world.monsters import build_monster
        brute = build_monster("wolf", (self.ox + 1, self.oy))
        self.engine.npc_manager.add_npc(brute)
        self.wmap.place_character(brute, *brute.position)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)
        # This test is about the shove DISTANCE, not the turn it triggers. Two
        # things otherwise make the final position non-deterministic across the
        # full suite: (1) the default player's class → STR mod varies with RNG
        # order (shifting the crit margin between a 1- and 2-tile shove); (2) shove
        # ends with advance_turn(), whose world tick can move the freshly-shoved
        # brute (e.g. a wolf now HUNTS wildlife, LIVING_WORLD C5). Pin the STR and
        # isolate the push from the incidental tick.
        self.player.strength = 16
        self.engine.advance_turn = lambda *a, **k: None
        shove(self.engine, rng=_SeqRng([20, 1]))
        self.assertEqual(brute.position, (self.ox + 3, self.oy),
                         "a crit shove is two tiles, not one")

    def test_crit_shove_loss_staggers_you(self):
        from engine.tactics import shove
        from world.monsters import build_monster
        brute = build_monster("wolf", (self.ox + 1, self.oy))
        self.engine.npc_manager.add_npc(brute)
        self.wmap.place_character(brute, *brute.position)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)
        shove(self.engine, rng=_SeqRng([1, 20]))
        self.assertEqual(self.player.position, (self.ox - 1, self.oy),
                         "a crit loss knocks YOU back")

    def test_forage_quality_degrees(self):
        self.wmap.terrain[self.oy][self.ox] = TerrainType.FOREST
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)
        self.player.inventory = []
        self.player.wisdom = 10
        fm = self.engine.forage_manager
        fm.rng = _FixedRng(20)
        msg = fm.forage(self.ox, self.oy)
        self.assertIn("perfect patch", msg.lower())
        # a perfect patch yields a bonus unit; identical raws now STACK (P25.1),
        # so count total units rather than inventory slots
        units = sum(getattr(it, "quantity", 1) for it in self.player.inventory)
        self.assertEqual(units, 2)
        fm.harvested_at = {}
        fm.rng = _FixedRng(1)
        hp0 = self.player.hp
        msg = fm.forage(self.ox, self.oy)
        self.assertIn("nettles", msg.lower())  # msg still says forage
        self.assertEqual(self.player.hp, hp0 - 1)
        units_after = sum(getattr(it, "quantity", 1)
                          for it in self.player.inventory)
        self.assertEqual(units_after, 2, "the fumble yields nothing")


if __name__ == "__main__":
    unittest.main()
