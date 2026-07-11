"""Squad/soldier model + battle field tests (P17.2)."""

import unittest

from engine.battle import BattleField, Soldier, Squad


class TestSquad(unittest.TestCase):
    def test_raising_a_squad(self):
        sq = Squad.raise_squad("s1", "red", "infantry_sword",
                               [(1, 1), (2, 1), (3, 1)])
        self.assertEqual(sq.strength, 3)
        self.assertEqual(sq.category, "infantry")
        self.assertEqual(sq.soldiers[0].max_hp, 20)
        self.assertTrue(sq.active)

    def test_one_morale_bar_for_the_body(self):
        sq = Squad.raise_squad("s1", "red", "infantry_sword",
                               [(1, 1), (2, 1)])
        self.assertEqual(sq.morale, 70)
        sq.adjust_morale(-60)     # crosses the threshold (25)
        self.assertTrue(sq.routed, "the squad, not a man, breaks")
        self.assertFalse(sq.active)

    def test_casualties_shrink_the_squad(self):
        sq = Squad.raise_squad("s1", "red", "infantry_sword",
                               [(1, 1), (2, 1), (3, 1)])
        sq.soldiers[0].hurt(999)
        self.assertEqual(sq.strength, 2)
        self.assertFalse(sq.soldiers[0].alive)

    def test_centroid(self):
        sq = Squad.raise_squad("s1", "red", "infantry_sword",
                               [(2, 2), (4, 2)])
        self.assertEqual(sq.centroid(), (3, 2))

    def test_orders_stick(self):
        sq = Squad.raise_squad("s1", "red", "infantry_sword",
                               [(1, 1)])
        sq.set_order("charge", "enemy_squad")
        self.assertEqual(sq.order, "charge")
        self.assertEqual(sq.order_target, "enemy_squad")

    def test_squad_round_trips(self):
        sq = Squad.raise_squad("s1", "blue", "cavalry_heavy",
                               [(5, 5), (6, 5)], commander=True)
        sq.adjust_morale(-10)
        sq.set_order("move", (10, 10))
        back = Squad.from_dict(sq.to_dict())
        self.assertEqual(back.squad_id, "s1")
        self.assertEqual(back.archetype, "cavalry_heavy")
        self.assertTrue(back.commander)
        self.assertEqual(back.morale, 60)
        self.assertEqual(back.order, "move")
        self.assertEqual(back.strength, 2)


class TestBattleField(unittest.TestCase):
    def test_occupancy_and_movement(self):
        bf = BattleField(10, 10)
        s = Soldier("a", "s1", "red", 1, 1, 20)
        self.assertTrue(bf.place(s))
        self.assertEqual(bf.soldier_at(1, 1), "a")
        self.assertTrue(bf.move_soldier(s, 2, 1))
        self.assertIsNone(bf.soldier_at(1, 1))
        self.assertEqual(bf.soldier_at(2, 1), "a")

    def test_no_two_soldiers_on_a_tile(self):
        bf = BattleField(10, 10)
        a = Soldier("a", "s1", "red", 1, 1, 20)
        b = Soldier("b", "s1", "red", 2, 1, 20)
        bf.place(a)
        bf.place(b)
        self.assertFalse(bf.move_soldier(b, 1, 1),
                         "you can't step onto an occupied tile")

    def test_walls_block_and_breach(self):
        bf = BattleField(10, 10)
        bf.add_wall(5, 5, "stone_wall")
        self.assertTrue(bf.is_blocking(5, 5))
        s = Soldier("a", "s1", "red", 4, 5, 20)
        bf.place(s)
        self.assertFalse(bf.move_soldier(s, 5, 5),
                         "the wall blocks")
        # batter it down
        breached = False
        for _ in range(20):
            if bf.damage_struct(5, 5, 50):
                breached = True
                break
        self.assertTrue(breached)
        self.assertEqual(bf.terrain[5][5], "rubble",
                         "a breach is a lane")
        self.assertTrue(bf.move_soldier(s, 5, 5),
                        "you can march the breach")

    def test_gate_is_weaker_than_wall(self):
        bf = BattleField(10, 10)
        bf.add_wall(1, 1, "stone_wall")
        bf.add_wall(2, 1, "gate")
        self.assertGreater(bf.struct_hp[(1, 1)],
                           bf.struct_hp[(2, 1)])

    def test_teams_and_enemies(self):
        bf = BattleField(20, 20)
        red = Squad.raise_squad("r", "red", "infantry_sword",
                                [(1, 1), (2, 1)])
        blue = Squad.raise_squad("b", "blue", "infantry_sword",
                                 [(18, 18), (17, 18)])
        bf.add_squad(red)
        bf.add_squad(blue)
        self.assertEqual(bf.teams(), ["blue", "red"])
        self.assertTrue(bf.team_active("red"))
        self.assertEqual([sq.squad_id for sq in bf.enemies_of("red")],
                         ["b"])

    def test_field_round_trips_mid_battle(self):
        bf = BattleField(12, 12)
        bf.add_wall(6, 6, "stone_wall")
        sq = Squad.raise_squad("r", "red", "archer_longbow",
                               [(1, 1), (2, 1)])
        sq.adjust_morale(-5)
        bf.add_squad(sq)
        bf.damage_struct(6, 6, 100)
        back = BattleField.from_dict(bf.to_dict())
        self.assertEqual(back.width, 12)
        self.assertEqual(back.struct_hp[(6, 6)], 400)
        self.assertIn("r", back.squads)
        self.assertEqual(back.squads["r"].morale, 65)
        self.assertEqual(back.squads["r"].strength, 2)


if __name__ == "__main__":
    unittest.main()
