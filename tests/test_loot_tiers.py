"""T1.1b — level/elite-scaled bonus gear drops."""

import random
import unittest

from items.loot_tables import _bonus_gear, TIER_LOOT, generate_loot


class _Foe:
    def __init__(self, level, elite=False, cls="monster"):
        self.level = level
        self.metadata = {"elite": True} if elite else {}
        self.character_class = type("K", (), {"value": cls})()


_EPIC_IDS = {i for t in ("epic", "legendary") for i, _ in TIER_LOOT[t]}


class TestLootTiers(unittest.TestCase):
    def test_weakling_never_drops_top_tier(self):
        rng = random.Random(3)
        drops = [_bonus_gear(_Foe(1), rng) for _ in range(400)]
        self.assertFalse(
            any(it and it.id in _EPIC_IDS for it in drops),
            "a level-1 foe never drops epic/legendary gear")

    def test_strong_elite_drops_quality_gear(self):
        rng = random.Random(4)
        got = [it for it in (_bonus_gear(_Foe(14, elite=True), rng)
                             for _ in range(400)) if it]
        self.assertGreater(len(got), 60, "a strong elite often yields gear")
        self.assertTrue(any(it.id in _EPIC_IDS for it in got),
                        "a strong elite can drop epic/legendary gear")

    def test_generate_loot_includes_the_bonus(self):
        # a high elite's full loot roll can contain a tier item
        rng = random.Random(5)
        ids = set()
        for _ in range(60):
            ids.update(i.id for i in generate_loot(_Foe(14, elite=True), rng))
        self.assertTrue(ids & _EPIC_IDS, "endgame loot rolls the new gear")


if __name__ == "__main__":
    unittest.main()
