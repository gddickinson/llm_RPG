"""Group AI skirmish tests (P17.3): the tick loop converges."""

import unittest

from engine.battle import BattleField, BattleSession, Squad


def _line(x, y0, n):
    return [(x, y0 + i) for i in range(n)]


def _skirmish(red_type="infantry_sword", red_n=6,
              blue_type="infantry_sword", blue_n=6, w=30, h=20):
    bf = BattleField(w, h)
    red = Squad.raise_squad("red1", "red", red_type,
                            _line(3, 6, red_n))
    blue = Squad.raise_squad("blue1", "blue", blue_type,
                             _line(w - 4, 6, blue_n))
    red.set_order("charge", "blue1")
    blue.set_order("charge", "red1")
    bf.add_squad(red)
    bf.add_squad(blue)
    return bf


class TestSkirmish(unittest.TestCase):
    def test_a_skirmish_converges_to_a_winner(self):
        bf = _skirmish()
        r = BattleSession(bf, seed=1).run_headless(max_ticks=300)
        self.assertIn(r["winner"], ("red", "blue"))
        self.assertLess(r["ticks"], 300, "it doesn't stall")

    def test_deterministic_by_seed(self):
        r1 = BattleSession(_skirmish(), seed=7).run_headless()
        r2 = BattleSession(_skirmish(), seed=7).run_headless()
        self.assertEqual(r1["winner"], r2["winner"])
        self.assertEqual(r1["ticks"], r2["ticks"])
        self.assertEqual(r1["survivors"], r2["survivors"])

    def test_the_bigger_side_usually_wins(self):
        wins = 0
        for seed in range(15):
            bf = _skirmish(red_n=10, blue_n=4)
            if BattleSession(bf, seed=seed).run_headless()[
                    "winner"] == "red":
                wins += 1
        self.assertGreaterEqual(wins, 12, "numbers tell on the grid")

    def test_soldiers_close_the_distance(self):
        bf = _skirmish()
        sess = BattleSession(bf, seed=3)
        red = bf.squads["red1"]
        blue = bf.squads["blue1"]
        gap0 = abs(red.centroid()[0] - blue.centroid()[0])
        for _ in range(6):
            if sess.over():
                break
            sess.tick()
        gap1 = abs((red.centroid() or (0, 0))[0] -
                   (blue.centroid() or (0, 0))[0])
        self.assertLess(gap1, gap0, "the lines advanced on each other")

    def test_a_broken_squad_routs_and_the_field_ends(self):
        # tiny vs huge: the small side should break, not fight forever
        bf = _skirmish(red_n=2, blue_n=14)
        r = BattleSession(bf, seed=5).run_headless(max_ticks=300)
        self.assertEqual(r["winner"], "blue")

    def test_archers_soften_a_charge(self):
        # archers with a head start should out-trade equal infantry
        ar_wins = 0
        for seed in range(15):
            bf = BattleField(30, 20)
            arch = Squad.raise_squad("a", "red", "archer_longbow",
                                     _line(3, 6, 8))
            inf = Squad.raise_squad("b", "blue", "infantry_sword",
                                    _line(26, 6, 8))
            arch.set_order("focus", "b")
            inf.set_order("charge", "a")
            bf.add_squad(arch)
            bf.add_squad(inf)
            if BattleSession(bf, seed=seed).run_headless()[
                    "winner"] == "red":
                ar_wins += 1
        # archers should win a fair share thanks to ranged volleys
        self.assertGreaterEqual(ar_wins, 6)

    def test_result_shape_matches_the_resolver(self):
        r = BattleSession(_skirmish(), seed=2).run_headless()
        for key in ("winner", "ticks", "survivors"):
            self.assertIn(key, r)
        self.assertEqual(set(r["survivors"]), {"red", "blue"})


if __name__ == "__main__":
    unittest.main()
