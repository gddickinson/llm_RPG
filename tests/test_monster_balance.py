"""P37.5b — the tougher wilderness monster balance (data-driven).

Locks in the buffed HP + combat stats on the COMMON wild foes so a future
data edit can't silently soften them back. The design contract: a SOLO wild
foe is a real but winnable fight for a geared low-level hero, while a PACK is
genuinely dangerous (you level up, gear up, or bring a party — power through
gear/party, not XP farming).
"""

import unittest

from world.monsters import build_monster


# (id, min_hp, needs_combat_stat) — the common encounter_weight>0 wild foes.
WILD_FOES = [
    ("wolf", 14, True),
    ("goblin", 11, True),
    ("bandit", 20, True),
    ("marsh_wisp", 12, True),
    ("bog_lurker", 28, True),
    ("wandering_troll", 44, True),
]


class TestMonsterBalance(unittest.TestCase):
    def test_wild_foes_carry_their_tougher_hp(self):
        for mid, min_hp, _ in WILD_FOES:
            m = build_monster(mid, (0, 0))
            self.assertGreaterEqual(
                m.hp, min_hp,
                f"{mid} should keep its P37.5b HP floor ({min_hp})")
            self.assertEqual(m.hp, m.max_hp, f"{mid} spawns at full HP")

    def test_wild_foes_have_real_combat_stats(self):
        # A default stat is 10; a buffed foe raises at least one offensive or
        # defensive score above the baseline so its hits/toughness bite.
        for mid, _, needs_stat in WILD_FOES:
            if not needs_stat:
                continue
            m = build_monster(mid, (0, 0))
            best = max(m.strength, m.dexterity, m.constitution)
            self.assertGreater(
                best, 10,
                f"{mid} should carry a real combat stat (>10), not all-10")

    def test_troll_is_an_apex_wild_threat(self):
        # The wandering troll is the fringe apex: much tougher than the L1 mobs.
        troll = build_monster("wandering_troll", (0, 0))
        wolf = build_monster("wolf", (0, 0))
        self.assertGreater(troll.hp, wolf.hp * 2)
        self.assertGreaterEqual(troll.strength, 16)

    def test_solo_foe_stays_winnable_for_a_geared_hero(self):
        # A rough duel model: a geared low-level hero (str 14, iron-sword tier,
        # ~20 HP) should reliably beat a lone wolf/goblin/bandit. This guards
        # against an over-buff that makes even a solo fight unwinnable.
        import random

        def duel(mid, trials=200):
            wins = 0
            for t in range(trials):
                random.seed(t)
                hp = 20
                m = build_monster(mid, (0, 0))
                mhp = m.hp
                dmg = lambda s, w=0: max(1, random.randint(1, 6) + w + (s - 10) // 2)
                r = 0
                while mhp > 0 and hp > 0 and r < 80:
                    r += 1
                    mhp -= dmg(14, 4)
                    if mhp > 0:
                        hp -= dmg(getattr(m, "strength", 10))
                if hp > 0 and mhp <= 0:
                    wins += 1
            return wins / trials

        for mid in ("wolf", "goblin", "bandit"):
            self.assertGreater(
                duel(mid), 0.8,
                f"a geared hero should usually win a solo {mid}")


class TestRosterDepth(unittest.TestCase):
    """T1.3 — mid-tier roster + dungeon depth-gating."""

    def test_dungeon_pool_depth_gates_tough_foes(self):
        from world.monsters import dungeon_pool
        shallow = dungeon_pool(1)
        deep = dungeon_pool(4)
        self.assertIn("ogre", shallow, "a min_depth-1 foe is available shallow")
        self.assertNotIn("stone_golem", shallow, "a deep foe is gated off floor 1")
        self.assertIn("stone_golem", deep, "a deep foe appears deep")
        self.assertGreater(len(deep), len(shallow))

    def test_midtier_dead_zone_filled(self):
        import json
        with open("data/monsters.json") as fh:
            d = json.load(fh)
        mid = [k for k, v in d.items() if 7 <= v.get("level", 1) <= 11]
        self.assertGreaterEqual(len(mid), 6, "the L7-11 dead zone is filled")


if __name__ == "__main__":
    unittest.main()
