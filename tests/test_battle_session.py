"""Group AI skirmish tests (P17.3): the tick loop converges."""

import unittest

from engine.battle import BattleField, BattleSession, Squad
from engine.battle import battle_ai as ai
from engine.battle import battle_orders as orders


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


class TestMovementSpeed(unittest.TestCase):
    """P17.4c: soldiers cover ground per their unit `speed`."""

    def _advance_after(self, utype, ticks):
        """Tiles a lone squad of `utype` advances toward a far, idle
        foe over `ticks` — measured before any contact."""
        bf = BattleField(48, 12)
        mover = Squad.raise_squad("m", "red", utype, [(2, 5), (2, 6)])
        foe = Squad.raise_squad("f", "blue", "infantry_sword",
                                [(46, 5), (46, 6)])
        foe.set_order("hold", "m")
        mover.set_order("charge", "f")
        bf.add_squad(mover)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=1)
        x0 = mover.centroid()[0]
        for _ in range(ticks):
            sess.tick()
        return mover.centroid()[0] - x0

    def test_cavalry_outruns_infantry(self):
        inf = self._advance_after("infantry_sword", 8)   # speed 1.0
        cav = self._advance_after("cavalry_light", 8)     # speed 2.0
        self.assertGreater(cav, inf * 1.5,
                           "horse should cover much more ground")

    def test_siege_crawls(self):
        cat = self._advance_after("siege_catapult", 8)    # speed 0.2
        inf = self._advance_after("infantry_sword", 8)
        self.assertLess(cat, inf, "a catapult is far slower than foot")
        self.assertGreaterEqual(cat, 1, "but it does inch forward")

    def test_speed_is_deterministic(self):
        a = self._advance_after("cavalry_light", 6)
        b = self._advance_after("cavalry_light", 6)
        self.assertEqual(a, b)

    def test_move_accum_survives_a_round_trip(self):
        bf = _skirmish(red_type="cavalry_light", red_n=4)
        sess = BattleSession(bf, seed=3)
        for _ in range(3):
            sess.tick()
        sq = bf.squads["red1"]
        before = [s.move_accum for s in sq.soldiers]
        restored = Squad.from_dict(sq.to_dict())
        after = [s.move_accum for s in restored.soldiers]
        self.assertEqual(before, after)


class TestOrders(unittest.TestCase):
    """P17.5: the commander's verbs actually change squad behaviour."""

    def _two(self, red_order, red_target=None, blue_order="hold"):
        bf = BattleField(40, 14)
        red = Squad.raise_squad("r", "red", "infantry_sword",
                                [(20, 6), (20, 7)])
        blue = Squad.raise_squad("b", "blue", "infantry_sword",
                                 [(6, 6), (6, 7)])
        red.set_order(red_order, red_target)
        blue.set_order(blue_order)
        bf.add_squad(red)
        bf.add_squad(blue)
        return bf, red, blue

    def test_intent_mapping(self):
        bf, red, _ = self._two("hold")
        self.assertEqual(orders.advance_intent(red), "hold")
        red.set_order("fallback")
        self.assertEqual(orders.advance_intent(red), "retreat")
        red.set_order("move", (10, 6))
        self.assertEqual(orders.advance_intent(red), "goto")
        red.set_order("charge")
        self.assertEqual(orders.advance_intent(red), "advance")
        red.set_order("move", "not_a_tile")   # bad target -> advance
        self.assertEqual(orders.advance_intent(red), "advance")

    def test_hold_roots_the_squad(self):
        bf, red, _ = self._two("hold")          # foe on hold too
        cx0 = red.centroid()[0]
        sess = BattleSession(bf, seed=1)
        for _ in range(8):
            sess.tick()
        self.assertEqual(red.centroid()[0], cx0,
                         "a holding squad does not advance")

    def test_fall_back_retreats_from_the_enemy(self):
        bf, red, _ = self._two("fallback")      # enemy is to the left
        cx0 = red.centroid()[0]
        sess = BattleSession(bf, seed=1)
        for _ in range(6):
            sess.tick()
        self.assertGreater(red.centroid()[0], cx0,
                           "fall-back withdraws away from the foe")

    def test_move_marches_to_the_ordered_tile(self):
        bf = BattleField(40, 20)
        red = Squad.raise_squad("r", "red", "infantry_sword",
                                [(5, 5), (5, 6)])
        # a distant idle foe off the path — must be ignored
        foe = Squad.raise_squad("b", "blue", "infantry_sword",
                                [(38, 18)])
        red.set_order("move", (25, 5))
        foe.set_order("hold")
        bf.add_squad(red)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=1)
        for _ in range(30):
            sess.tick()
        self.assertGreaterEqual(red.centroid()[0], 20,
                                "the squad marched toward its tile")

    def test_focus_fire_concentrates_on_the_ordered_squad(self):
        bf = BattleField(40, 14)
        me = Squad.raise_squad("me", "red", "infantry_sword", [(20, 6)])
        ordered = Squad.raise_squad("ordered", "blue",
                                    "infantry_sword", [(30, 6)])   # far
        other = Squad.raise_squad("other", "blue", "infantry_sword",
                                  [(22, 6)])                        # near
        me.set_order("focus_fire", "ordered")
        for sq in (me, ordered, other):
            bf.add_squad(sq)
        tgt = ai.pick_target(bf, me.soldiers[0], me)
        self.assertEqual(tgt.squad_id, "ordered",
                         "focus fire beats the closer squad")

    def test_focus_legacy_spelling_still_works(self):
        self.assertTrue(orders.is_focus("focus"))
        self.assertTrue(orders.is_focus("focus_fire"))
        self.assertFalse(orders.is_focus("charge"))

    def test_valid_order(self):
        for o in orders.ORDERS:
            self.assertTrue(orders.valid_order(o))
        self.assertTrue(orders.valid_order("focus"))
        self.assertFalse(orders.valid_order("nonsense"))


if __name__ == "__main__":
    unittest.main()
