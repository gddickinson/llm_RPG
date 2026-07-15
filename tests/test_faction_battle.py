"""Fold-back (P17.8): off-screen faction skirmishes settled by the real
Lanchester resolver — a faction's strength dressed as an army, fought,
and the survivor ratios read back."""

import random
import unittest

from engine import faction_battle as fb


class TestArmyFor(unittest.TestCase):
    def test_more_strength_more_bodies(self):
        weak = fb.army_for("guards", 10)
        strong = fb.army_for("guards", 90)
        self.assertGreater(strong.survivors(), weak.survivors())

    def test_roster_matches_the_faction(self):
        guards = fb.army_for("guards", 60)
        cats = {u.category for u in guards.units}
        self.assertIn("archer", cats, "guards field bowmen")
        brig = fb.army_for("brigands", 60)
        self.assertIn("cavalry", {u.category for u in brig.units},
                      "brigands field horse")

    def test_unknown_faction_falls_back(self):
        army = fb.army_for("goblins_of_nowhere", 40)
        self.assertGreater(army.survivors(), 0)

    def test_a_spent_faction_still_fields_a_token_force(self):
        army = fb.army_for("guards", 5)
        self.assertGreaterEqual(army.survivors(), 1)


class TestResolveRaid(unittest.TestCase):
    def test_the_stronger_side_wins(self):
        res = fb.resolve_raid("brigands", 80, "guards", 20,
                              random.Random(1))
        self.assertEqual(res["winner"], "brigands")

    def test_ratios_are_bounded(self):
        res = fb.resolve_raid("brigands", 50, "guards", 50,
                              random.Random(3))
        for k in ("atk_ratio", "def_ratio"):
            self.assertGreaterEqual(res[k], 0.0)
            self.assertLessEqual(res[k], 1.0)

    def test_the_winner_is_mauled_less(self):
        res = fb.resolve_raid("brigands", 85, "guards", 20,
                              random.Random(2))
        # brigands win; they keep a larger share of their army than the
        # guards they overran
        self.assertGreater(res["atk_ratio"], res["def_ratio"])

    def test_deterministic_for_a_seed(self):
        a = fb.resolve_raid("guards", 55, "brigands", 45, random.Random(7))
        b = fb.resolve_raid("guards", 55, "brigands", 45, random.Random(7))
        self.assertEqual(a["winner"], b["winner"])
        self.assertEqual(a["atk_survivors"], b["atk_survivors"])


class TestTickerFoldBack(unittest.TestCase):
    def _ticker(self):
        from engine.faction_ticker import FactionTicker
        return FactionTicker(engine=None, seed=1)

    def test_overwhelming_brigands_get_away(self):
        t = self._ticker()
        t.state["brigands"]["strength"] = 95
        t.state["guards"]["strength"] = 8
        self.assertIn("got away", t._brigand_raid()[0])

    def test_a_strong_guard_repels_and_bloodies_the_raiders(self):
        t = self._ticker()
        t.state["brigands"]["strength"] = 12
        t.state["guards"]["strength"] = 95
        b0 = t.state["brigands"]["strength"]
        notes = t._brigand_raid()
        self.assertIn("repelled", notes[0])
        self.assertLess(t.state["brigands"]["strength"], b0,
                        "the beaten raiders shed strength")

    def test_casualty_hit_is_bounded(self):
        from engine.faction_ticker import FactionTicker
        self.assertEqual(FactionTicker._casualty_hit(1.0), 1)   # untouched
        self.assertEqual(FactionTicker._casualty_hit(0.0), 10)  # wiped
        self.assertTrue(1 <= FactionTicker._casualty_hit(0.5) <= 10)


class TestSiegeFold(unittest.TestCase):
    """P17.8c: a castle assault settled off-screen through the resolver's
    siege math — the defender fights from behind walls."""

    def test_walls_turn_a_losing_garrison_into_a_holding_one(self):
        # in the open the crown garrison loses to a stronger rabble...
        openf = fb.resolve_raid("brigands", 60, "crown", 45,
                                random.Random(0))
        self.assertEqual(openf["winner"], "brigands",
                         "open field: numbers tell")
        # ...but behind its walls, with no siege engines against it, it holds
        walled = fb.resolve_siege("brigands", 60, "crown", 45,
                                  random.Random(0))
        self.assertEqual(walled["winner"], "crown",
                         "the wall keeps the rabble out")

    def test_a_rabble_cannot_breach_a_wall(self):
        res = fb.resolve_siege("brigands", 70, "crown", 40,
                               random.Random(1))
        self.assertFalse(res["breached"],
                         "no engines, no breach — the wall stands")

    def test_a_besieging_host_with_engines_breaches(self):
        res = fb.resolve_siege("besiegers", 60, "crown", 45,
                               random.Random(2))
        self.assertTrue(res["breached"],
                        "rams and catapults batter the wall down")

    def test_the_defender_carries_a_fort(self):
        army = fb.army_for("crown", 50, forts=["stone_wall"])
        self.assertEqual(len(army.forts), 1)
        self.assertEqual(army.forts[0].fort_type, "stone_wall")

    def test_deterministic_for_a_seed(self):
        a = fb.resolve_siege("besiegers", 55, "crown", 50, random.Random(7))
        b = fb.resolve_siege("besiegers", 55, "crown", 50, random.Random(7))
        self.assertEqual(a["winner"], b["winner"])
        self.assertEqual(a["breached"], b["breached"])


class TestMonsterIncursionFold(unittest.TestCase):
    def _ticker(self):
        from engine.faction_ticker import FactionTicker
        return FactionTicker(engine=None, seed=1)

    def test_a_beast_tide_presses_in(self):
        t = self._ticker()
        t.state["monsters"]["strength"] = 95
        t.state["villagers"]["strength"] = 8
        self.assertIn("pressed in", t._monster_incursion()[0])

    def test_the_militia_drives_the_beasts_back(self):
        t = self._ticker()
        t.state["monsters"]["strength"] = 10
        t.state["villagers"]["strength"] = 95
        m0 = t.state["monsters"]["strength"]
        notes = t._monster_incursion()
        self.assertIn("drove the beasts back", notes[0])
        self.assertLess(t.state["monsters"]["strength"], m0,
                        "the broken warband loses strength")

    def test_clash_helper_returns_a_faction_winner(self):
        t = self._ticker()
        res = t._clash("brigands", "guards")
        self.assertIn(res["winner"], ("brigands", "guards", None))


if __name__ == "__main__":
    unittest.main()
