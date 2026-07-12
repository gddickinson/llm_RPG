"""Area effects & battle magic (P17.12): a blast hits a cluster (fiercest
at the impact), a fireball paints the surface layer and ignores armour,
a war-mage casts it in a real battle, and a catapult splashes the ranks."""

import unittest

from engine.battle import BattleField, Squad, BattleSession
from engine.battle import battle_aoe as aoe


def _sq(archetype, cells, team="red", sid="s"):
    return Squad.raise_squad(sid, team, archetype, cells)


class TestGeometry(unittest.TestCase):
    def test_radius_cluster(self):
        bf = BattleField(12, 12)
        self.assertEqual(len(aoe.tiles_in_radius(bf, 5, 5, 1)), 9)
        self.assertEqual(len(aoe.tiles_in_radius(bf, 5, 5, 0)), 1)

    def test_clamped_in_bounds(self):
        bf = BattleField(12, 12)
        # a corner burst only counts on-field tiles
        self.assertEqual(len(aoe.tiles_in_radius(bf, 0, 0, 1)), 4)


class TestBlast(unittest.TestCase):
    def test_fiercest_at_the_impact(self):
        bf = BattleField(16, 8)
        near = _sq("infantry_sword", [(6, 4)], team="blue", sid="n")
        far = _sq("infantry_sword", [(8, 4)], team="blue", sid="f")
        bf.add_squad(near)
        bf.add_squad(far)
        hp_near0, hp_far0 = near.soldiers[0].hp, far.soldiers[0].hp
        aoe.blast(bf, 6, 4, 2, 12)                 # impact on the near man
        dmg_near = hp_near0 - near.soldiers[0].hp
        dmg_far = hp_far0 - far.soldiers[0].hp
        self.assertGreater(dmg_near, dmg_far, "the blast fades outward")
        self.assertGreater(dmg_far, 0, "but the edge still stings")

    def test_blast_cracks_structures(self):
        bf = BattleField(10, 8)
        bf.add_wall(5, 4, "gate")
        hp0 = bf.struct_hp[(5, 4)]
        aoe.blast(bf, 5, 4, 1, 20)
        self.assertLess(bf.struct_hp.get((5, 4), 0), hp0)

    def test_hit_structs_off_spares_the_wall(self):
        bf = BattleField(10, 8)
        bf.add_wall(5, 4, "gate")
        hp0 = bf.struct_hp[(5, 4)]
        aoe.blast(bf, 5, 4, 1, 20, hit_structs=False)
        self.assertEqual(bf.struct_hp[(5, 4)], hp0)

    def test_blast_reports_kills(self):
        bf = BattleField(10, 8)
        weak = _sq("archer_longbow", [(5, 4)], team="blue")
        bf.add_squad(weak)
        weak.soldiers[0].hp = 3
        hit, killed = aoe.blast(bf, 5, 4, 1, 30)
        self.assertEqual(hit, 1)
        self.assertEqual(killed, 1)


class TestFireball(unittest.TestCase):
    def test_fireball_paints_fire(self):
        bf = BattleField(12, 8)
        aoe.fireball(bf, 6, 4, radius=1)
        self.assertEqual(bf.surfaces[(6, 4)]["kind"], "fire")
        self.assertEqual(bf.surfaces[(7, 4)]["kind"], "fire")

    def test_flame_ignores_armour(self):
        # a plated knight and an unarmoured archer take the SAME fire hit
        bf = BattleField(16, 8)
        knight = _sq("cavalry_heavy", [(4, 4)], team="blue", sid="k")
        arch = _sq("archer_longbow", [(10, 4)], team="blue", sid="a")
        bf.add_squad(knight)
        bf.add_squad(arch)
        hk0, ha0 = knight.soldiers[0].hp, arch.soldiers[0].hp
        aoe.blast(bf, 4, 4, 0, 8, damage_type="fire")
        aoe.blast(bf, 10, 4, 0, 8, damage_type="fire")
        self.assertEqual(hk0 - knight.soldiers[0].hp,
                         ha0 - arch.soldiers[0].hp,
                         "fire burns plate and cloth alike")

    def test_cast_oil_slicks_ground(self):
        bf = BattleField(12, 8)
        aoe.cast(bf, "oil", 6, 4, 1, 8)
        self.assertEqual(bf.surfaces[(6, 4)]["kind"], "oil")


class TestInBattle(unittest.TestCase):
    def test_a_war_mage_scorches_a_cluster(self):
        bf = BattleField(20, 10)
        mage = _sq("battle_mage", [(3, 5)], team="red", sid="m")
        # a packed 3x3 block of foot inside the mage's reach
        block = [(x, y) for x in range(9, 12) for y in range(4, 7)]
        foe = _sq("infantry_sword", block, team="blue", sid="foe")
        foe.set_order("hold", "m")
        bf.add_squad(mage)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=1)
        hp_total0 = sum(s.hp for s in foe.alive_soldiers)
        for _ in range(4):
            sess.tick()
        hurt = sum(1 for s in foe.soldiers
                   if s.alive and s.hp < s.max_hp) + \
            sum(1 for s in foe.soldiers if not s.alive)
        self.assertGreater(hurt, 1, "the fireball caught several at once")
        self.assertTrue(any(v["kind"] == "fire"
                            for v in bf.surfaces.values()),
                        "and left the ground ablaze")

    def test_catapult_splashes_the_ranks_by_the_wall(self):
        bf = BattleField(24, 10)
        bf.add_wall(14, 5, "stone_wall")
        cat = _sq("siege_catapult", [(4, 5)], team="red", sid="c")
        cat.set_order("charge", "d")
        # a defender pressed right against the wall, inside the blast
        d = _sq("infantry_sword", [(15, 5)], team="blue", sid="d")
        d.set_order("hold", "c")
        bf.add_squad(cat)
        bf.add_squad(d)
        sess = BattleSession(bf, seed=1)
        hp0 = d.soldiers[0].hp
        for _ in range(6):
            sess.tick()
        self.assertLess(d.soldiers[0].hp, hp0,
                        "the stone crumped the man beside the wall")


if __name__ == "__main__":
    unittest.main()
