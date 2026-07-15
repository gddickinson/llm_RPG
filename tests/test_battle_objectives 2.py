"""Capture-point victory (P17.6c): a squad holding an objective wins
without wiping out the enemy."""

import unittest

from engine.battle import BattleField, BattleSession, Squad
from engine.battle.battle_scenario import build_field


def _field_with_point(hold=8, radius=2):
    bf = BattleField(30, 20)
    bf.add_objective("hill", (15, 10), radius=radius, hold=hold)
    return bf


class TestObjectiveModel(unittest.TestCase):
    def test_team_counts_near(self):
        bf = _field_with_point()
        red = Squad.raise_squad("r", "red", "infantry_sword",
                                [(15, 10), (16, 10)])
        blue = Squad.raise_squad("b", "blue", "infantry_sword",
                                 [(27, 18)])           # far away
        bf.add_squad(red)
        bf.add_squad(blue)
        counts = bf.team_counts_near((15, 10), 2)
        self.assertEqual(counts.get("red"), 2)
        self.assertNotIn("blue", counts)

    def test_dominant_needs_a_strict_lead(self):
        self.assertEqual(BattleSession._dominant({"red": 3, "blue": 1}),
                         "red")
        self.assertIsNone(BattleSession._dominant({"red": 2, "blue": 2}))
        self.assertIsNone(BattleSession._dominant({}))


class TestCaptureVictory(unittest.TestCase):
    def test_holding_a_point_wins_without_a_massacre(self):
        bf = _field_with_point(hold=8)
        red = Squad.raise_squad("r", "red", "infantry_sword",
                                [(15, 10), (15, 11)])
        blue = Squad.raise_squad("b", "blue", "infantry_sword",
                                 [(27, 18), (27, 17)])
        red.set_order("hold")
        blue.set_order("hold")            # both idle; red sits the point
        bf.add_squad(red)
        bf.add_squad(blue)
        r = BattleSession(bf, seed=1).run_headless(max_ticks=40)
        self.assertEqual(r["winner"], "red")
        self.assertEqual(r["objective"], "red")
        self.assertTrue(bf.team_active("blue"),
                        "blue was NOT eliminated — capture won it")
        self.assertLessEqual(r["ticks"], 12)

    def test_contested_point_does_not_capture(self):
        bf = _field_with_point(hold=6)
        red = Squad.raise_squad("r", "red", "infantry_sword",
                                [(14, 10)])
        blue = Squad.raise_squad("b", "blue", "infantry_sword",
                                 [(16, 10)])          # equal, in radius
        red.set_order("hold")
        blue.set_order("hold")
        bf.add_squad(red)
        bf.add_squad(blue)
        sess = BattleSession(bf, seed=1)
        for _ in range(10):
            sess.tick()
        self.assertIsNone(bf.objectives[0]["captured_by"],
                          "a tie in the radius makes no progress")

    def test_objectives_round_trip(self):
        bf = _field_with_point()
        red = Squad.raise_squad("r", "red", "infantry_sword",
                                [(15, 10)])
        bf.add_squad(red)
        BattleSession(bf, seed=1).tick()          # move the meter
        restored = BattleField.from_dict(bf.to_dict())
        self.assertEqual(restored.objectives, bf.objectives)


class TestCaptureScenario(unittest.TestCase):
    def test_seize_the_hill_builds_a_point(self):
        bf = build_field("seize_the_hill")
        self.assertEqual(len(bf.objectives), 1)
        self.assertEqual(bf.objectives[0]["id"], "hill")

    def test_seize_the_hill_is_won_by_capture(self):
        r = BattleSession(build_field("seize_the_hill"),
                          seed=0).run_headless(max_ticks=400)
        self.assertEqual(r["winner"], "red")
        self.assertEqual(r["objective"], "red")


if __name__ == "__main__":
    unittest.main()
