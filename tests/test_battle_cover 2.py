"""Cover (P17.6a): terrain blunts RANGED fire, not melee."""

import random
import unittest

from engine.battle import BattleField, BattleSession, Squad
from engine.battle import battle_ai as ai
from engine.battle.battle_data import terrain_cover
from engine.battle.battle_scenario import build_field


def _hits(terrain, gap, atk_type, rolls=2000):
    """Count how often a lone attacker of `atk_type` wounds a lone
    target `gap` tiles away standing on `terrain`, over `rolls`."""
    bf = BattleField(16, 5)
    if terrain != "grass":
        bf.set_terrain(2 + gap, 2, terrain)
    atk = Squad.raise_squad("a", "red", atk_type, [(2, 2)])
    tgt = Squad.raise_squad("b", "blue", "infantry_sword",
                            [(2 + gap, 2)])
    bf.add_squad(atk)
    bf.add_squad(tgt)
    sol, t = atk.soldiers[0], tgt.soldiers[0]
    rng = random.Random(0)
    hits = 0
    for _ in range(rolls):
        t.hp, t.alive = t.max_hp, True
        before = t.hp
        ai.attack(bf, sol, atk, t, rng)
        if t.hp < before:
            hits += 1
    return hits


class TestCoverData(unittest.TestCase):
    def test_cover_values(self):
        self.assertEqual(terrain_cover("grass"), 0.0)
        self.assertGreater(terrain_cover("forest"), terrain_cover("rubble"))
        self.assertGreater(terrain_cover("rubble"), 0.0)
        self.assertEqual(terrain_cover("nonsense"), 0.0)

    def test_field_cover_at(self):
        bf = BattleField(6, 6)
        bf.set_terrain(3, 3, "forest")
        self.assertGreater(bf.cover_at(3, 3), 0.0)
        self.assertEqual(bf.cover_at(0, 0), 0.0)      # grass
        self.assertEqual(bf.cover_at(-1, 0), 0.0)     # off-field


class TestCoverEffect(unittest.TestCase):
    def test_cover_reduces_ranged_hits(self):
        open_hits = _hits("grass", 4, "archer_longbow")
        wood_hits = _hits("forest", 4, "archer_longbow")
        self.assertLess(wood_hits, open_hits,
                        "the treeline should shield the target")

    def test_more_cover_shields_more(self):
        light = _hits("rubble", 4, "archer_longbow")   # 0.3
        heavy = _hits("forest", 4, "archer_longbow")    # 0.5
        self.assertLess(heavy, light, "deeper cover, fewer hits")

    def test_cover_does_not_shield_melee(self):
        grass = _hits("grass", 1, "infantry_sword")
        wood = _hits("forest", 1, "infantry_sword")
        # a swordsman in the trees is no harder to hit hand-to-hand
        self.assertLess(abs(wood - grass), 90,
                        "cover must not blunt melee")


class TestCoverScenario(unittest.TestCase):
    def test_treeline_paints_forest_under_the_archers(self):
        bf = build_field("treeline_defense")
        bows = bf.squads["blue_bows"]
        in_cover = sum(1 for s in bows.alive_soldiers
                       if bf.cover_at(s.x, s.y) > 0)
        self.assertEqual(in_cover, bows.strength,
                         "every archer stands in the wood")

    def test_treeline_converges(self):
        r = BattleSession(build_field("treeline_defense"),
                          seed=2).run_headless(max_ticks=400)
        self.assertIn("winner", r)
        self.assertLessEqual(r["ticks"], 400)


if __name__ == "__main__":
    unittest.main()
