"""Battle auto-resolver tests (P17.1): the Lanchester foundation."""

import unittest

from engine.battle import Army, resolve, unit_category
from engine.battle.battle_data import (FORMATIONS, MATCHUP, UNITS)


class TestBattleData(unittest.TestCase):
    def test_the_tables_loaded(self):
        self.assertIn("infantry_sword", UNITS)
        self.assertIn("cavalry_heavy", UNITS)
        self.assertIn("siege_trebuchet", UNITS)
        self.assertIn("shield_wall", FORMATIONS)
        self.assertEqual(MATCHUP["cavalry|archer"], 1.5)

    def test_categories(self):
        self.assertEqual(unit_category("cavalry_light"), "cavalry")
        self.assertEqual(unit_category("archer_longbow"), "archer")
        self.assertEqual(unit_category("siege_ram"), "siege")


class TestResolve(unittest.TestCase):
    def test_deterministic_by_seed(self):
        def fight():
            a = Army.make("A", [("infantry_sword", 50)])
            b = Army.make("B", [("infantry_sword", 40)])
            return resolve(a, b, seed=42)
        r1, r2 = fight(), fight()
        self.assertEqual(r1["winner"], r2["winner"])
        self.assertEqual(r1["attacker_survivors"],
                         r2["attacker_survivors"])
        self.assertEqual(r1["rounds"], r2["rounds"])

    def test_the_bigger_infantry_line_usually_wins(self):
        wins = 0
        for seed in range(20):
            a = Army.make("Big", [("infantry_sword", 80)])
            b = Army.make("Small", [("infantry_sword", 30)])
            if resolve(a, b, seed=seed)["winner"] == "Big":
                wins += 1
        self.assertGreaterEqual(wins, 18,
                                "numbers tell in a straight melee")

    def test_cavalry_crushes_archers_in_the_open(self):
        # equal points; RPS + terrain should favor the horse
        wins = 0
        for seed in range(20):
            horse = Army.make("Horse", [("cavalry_heavy", 30)])
            bows = Army.make("Bows", [("archer_longbow", 40)])
            if resolve(horse, bows, terrain="plains",
                       seed=seed)["winner"] == "Horse":
                wins += 1
        self.assertGreaterEqual(wins, 15,
                                "cavalry beats archers on plains")

    def test_spears_blunt_the_charge(self):
        # spears' bonus_vs_cavalry should turn the same fight
        cav_wins_vs_sword = 0
        cav_wins_vs_spear = 0
        for seed in range(20):
            h1 = Army.make("H", [("cavalry_heavy", 30)])
            sword = Army.make("S", [("infantry_sword", 40)])
            if resolve(h1, sword, seed=seed)["winner"] == "H":
                cav_wins_vs_sword += 1
            h2 = Army.make("H", [("cavalry_heavy", 30)])
            spear = Army.make("P", [("infantry_spear", 40)])
            if resolve(h2, spear, seed=seed)["winner"] == "H":
                cav_wins_vs_spear += 1
        self.assertGreater(cav_wins_vs_sword, cav_wins_vs_spear,
                           "spears cost the cavalry the charge")

    def test_a_commander_bonus_helps(self):
        led = 0
        for seed in range(20):
            a = Army.make("Led", [("infantry_sword", 40)],
                          commander_bonus=0.3)
            b = Army.make("Rabble", [("infantry_sword", 40)])
            if resolve(a, b, seed=seed)["winner"] == "Led":
                led += 1
        self.assertGreaterEqual(led, 14,
                                "leadership tips an even fight")

    def test_a_shield_wall_holds(self):
        # same troops, one in shield_wall: the formation's DEFENCE
        # should win the attrition against a loose line
        held = 0
        for seed in range(20):
            wall = Army.make("Wall", [("infantry_sword", 40)],
                             form="shield_wall")
            open_ = Army.make("Open", [("infantry_sword", 40)])
            r = resolve(wall, open_, seed=seed)
            if r["winner"] == "Wall":
                held += 1
        self.assertGreaterEqual(held, 12,
                                "the wall's defence wins attrition")

    def test_siege_breaches_the_wall(self):
        breached = 0
        for seed in range(10):
            besiegers = Army.make(
                "Siege", [("siege_trebuchet", 4),
                          ("infantry_sword", 60)])
            garrison = Army.make(
                "Keep", [("archer_longbow", 15)],
                forts=["stone_wall", "gate"])
            r = resolve(besiegers, garrison, is_siege=True,
                        seed=seed, max_rounds=20)
            if r["breached"]:
                breached += 1
        self.assertGreaterEqual(breached, 8,
                                "engines bring the walls down")

    def test_a_battle_terminates(self):
        a = Army.make("A", [("infantry_sword", 100)])
        b = Army.make("B", [("infantry_sword", 100)])
        r = resolve(a, b, seed=1, max_rounds=12)
        self.assertLessEqual(r["rounds"], 12)
        self.assertIsNotNone(r["winner"])

    def test_off_screen_helper_shape(self):
        # the result dict is what faction systems will read
        r = resolve(Army.make("A", [("cavalry_light", 20)]),
                    Army.make("B", [("infantry_pike", 20)]), seed=3)
        for key in ("winner", "rounds", "attacker_survivors",
                    "defender_survivors", "breached"):
            self.assertIn(key, r)


if __name__ == "__main__":
    unittest.main()
