"""The Siege of Bloodstone (P17.8b / P18.6b): a castle assault that reuses
the P17 siege field — stone walls, gate, towers and boiling oil, a
garrison defending, a host with rams and catapults breaching in."""

import unittest

from engine.battle.battle_scenario import SCENARIOS, build_field
from engine.battle import BattleSession


def _kinds(field, kind):
    return [k for k in field.struct_hp if field.struct_kind.get(k) == kind]


class TestSiegeField(unittest.TestCase):
    def test_the_scenario_ships(self):
        self.assertIn("castle_siege", SCENARIOS)

    def test_the_castle_has_stone_walls_a_gate_and_towers(self):
        bf = build_field("castle_siege")
        self.assertGreater(len(_kinds(bf, "stone_wall")), 20,
                           "a real curtain wall")
        self.assertEqual(len(_kinds(bf, "gate")), 1, "one gatehouse")
        self.assertGreaterEqual(len(_kinds(bf, "tower")), 4, "corner towers")
        self.assertGreaterEqual(len(_kinds(bf, "boiling_oil")), 1,
                                "oil over the gate")

    def test_both_the_garrison_and_the_host_take_the_field(self):
        bf = build_field("castle_siege")
        teams = {sq.team for sq in bf.squads.values()}
        self.assertEqual(teams, {"red", "blue"})
        # the host brings siege engines to breach the wall
        cats = [sq for sq in bf.squads.values()
                if sq.stats.get("structural_dmg", 0) > 0]
        self.assertTrue(cats, "besiegers field rams/catapults")


class TestSiegePlays(unittest.TestCase):
    def test_the_siege_resolves(self):
        r = BattleSession(build_field("castle_siege"),
                          seed=1).run_headless(max_ticks=1200)
        self.assertIn(r["winner"], ("red", "blue"), "someone wins")

    def test_the_gate_is_battered_down(self):
        # the defining siege beat: the rams/catapults breach the gate,
        # so the fight doesn't just play out in the open
        bf = build_field("castle_siege")
        gate0 = len(_kinds(bf, "gate"))
        self.assertEqual(gate0, 1)
        BattleSession(bf, seed=1).run_headless(max_ticks=1200)
        self.assertEqual(len(_kinds(bf, "gate")), 0,
                         "the gatehouse is breached")

    def test_even_the_victors_pay_for_the_walls(self):
        bf = build_field("castle_siege")
        start = {sq.squad_id: sq.strength for sq in bf.squads.values()}
        r = BattleSession(bf, seed=2).run_headless(max_ticks=1200)
        won = r["winner"]
        winner_start = sum(v for sid, v in start.items()
                           if bf.squads[sid].team == won)
        winner_left = sum(sq.strength for sq in bf.squads.values()
                          if sq.team == won)
        self.assertLess(winner_left, winner_start,
                        "the walls and the oil exact a toll even in victory")


if __name__ == "__main__":
    unittest.main()
