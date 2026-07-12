"""P28.2a — mounts of every kind (data-driven roster).

The pack mule generalises to a roster (mule/donkey/horse/war-horse/elephant/
magic carpet): buy one at the right seller, it hauls extra load and trails a
step behind. Honours the legacy P15.8b mule flag.
"""

import unittest

from engine.game_engine import GameEngine
from engine import mounts
from engine.carry import capacity
from world.location import Location


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.p.gold = 2000

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _clear_sellers(self):
        """Remove every real seller so only a planted one counts (Oakvale
        ships a market stall near the start)."""
        keep = []
        for loc in self.engine.world.locations:
            name = (loc.name or "").lower()
            typ = (loc.properties or {}).get("type", "")
            if any(k in name or typ == k
                   for k in ("stable", "market", "bazaar")):
                continue
            keep.append(loc)
        self.engine.world.locations[:] = keep

    def _seller(self, kind_word):
        self._clear_sellers()
        px, py = self.p.position
        loc = Location(f"Test {kind_word}", "", px + 1, py, 1, 1)
        loc.add_property("type", kind_word)
        self.engine.world.add_location(loc)


class TestRoster(unittest.TestCase):
    def test_the_roster_loads(self):
        self.assertGreaterEqual(len(mounts.all_mounts()), 5)
        self.assertIn("horse", mounts.all_mounts())

    def test_specs_expose_carry_cost_speed(self):
        self.assertEqual(mounts.carry_of("mule"), 8)   # matches P15.8b
        self.assertGreater(mounts.cost_of("war_horse"), mounts.cost_of("horse"))
        self.assertGreaterEqual(mounts.speed_of("horse"), 1.0)

    def test_a_carpet_flies_over_barriers(self):
        self.assertIn("water", mounts.traverses("magic_carpet"))
        self.assertIn("mountain", mounts.traverses("magic_carpet"))

    def test_an_unknown_kind_is_empty(self):
        self.assertEqual(mounts.mount_spec("griffon"), {})


class TestBuying(_Base):
    def test_buy_a_horse_at_a_stable(self):
        self._seller("stable")
        g0 = self.p.gold
        msg = mounts.buy_mount(self.engine, "horse")
        self.assertIn("horse", msg.lower())
        self.assertEqual(mounts.active_mount(self.p), "horse")
        self.assertEqual(self.p.gold, g0 - mounts.cost_of("horse"))

    def test_no_seller_no_sale(self):
        self._clear_sellers()            # no stable (or any seller) nearby
        msg = mounts.buy_mount(self.engine, "horse")
        self.assertIsNone(mounts.active_mount(self.p))
        self.assertIn("stable", msg.lower())

    def test_wrong_seller_kind_refuses(self):
        self._seller("stable")           # a stable, but an elephant needs a market
        msg = mounts.buy_mount(self.engine, "elephant")
        self.assertIsNone(mounts.active_mount(self.p))
        self.assertIn("market", msg.lower())

    def test_cannot_afford(self):
        self._seller("market")
        self.p.gold = 5
        mounts.buy_mount(self.engine, "elephant")
        self.assertIsNone(mounts.active_mount(self.p))

    def test_only_one_mount_at_a_time(self):
        self._seller("stable")
        mounts.buy_mount(self.engine, "horse")
        msg = mounts.buy_mount(self.engine, "mule")
        self.assertEqual(mounts.active_mount(self.p), "horse")
        self.assertIn("already", msg.lower())


class TestEffects(_Base):
    def test_a_mount_hauls_extra(self):
        base = capacity(self.p)
        self._seller("stable")
        mounts.buy_mount(self.engine, "donkey")     # carry 10
        self.assertEqual(capacity(self.p) - base, mounts.carry_of("donkey"))

    def test_the_mount_trails_behind(self):
        self._seller("stable")
        mounts.buy_mount(self.engine, "horse")
        old = tuple(self.p.position)
        self.p.position = (old[0] + 1, old[1])
        mounts.mount_follow(self.engine, old)
        self.assertEqual(mounts.mount_position(self.engine), old)

    def test_release_parts_ways(self):
        self._seller("stable")
        mounts.buy_mount(self.engine, "horse")
        mounts.release_mount(self.engine)
        self.assertIsNone(mounts.active_mount(self.p))
        self.assertFalse(self.p.metadata.get("mounted"))

    def test_legacy_mule_flag_is_honoured(self):
        # an old save with the P15.8b flag still hauls +8
        base_no = capacity(self.p)
        self.p.metadata["mule"] = {"pos": list(self.p.position)}
        self.assertEqual(mounts.active_mount(self.p), "mule")
        self.assertEqual(capacity(self.p) - base_no, 8)


if __name__ == "__main__":
    unittest.main()
