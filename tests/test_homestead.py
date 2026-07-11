"""Claim a home (P15.7): buy a derelict, repair it, live in it."""

import json
import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine            # noqa: E402
from engine import homestead                         # noqa: E402
from engine.furniture import _kind                   # noqa: E402
from items.item_registry import create_item          # noqa: E402
from world.location import Location                  # noqa: E402
from world.interiors import Interior                 # noqa: E402


def _enter_derelict(engine, name="Old Shack", w=6, h=5):
    """Drop the player inside a fresh unowned derelict building."""
    loc = Location(name, "A tumbledown shack.", 5, 5, w, h)
    loc.add_property("derelict", True)
    engine.world.locations.append(loc)
    inter = Interior(name=name, width=w, height=h,
                     description="Dust lies thick — no one lives here.",
                     door=(w // 2, h - 1))
    inter.init_grid()
    engine.interiors[name] = inter
    engine.current_interior = inter
    engine.player.position = (1, 1)
    return loc, inter


def _stock(engine, gold=500, wood=9, stone=6):
    p = engine.player
    p.gold = gold
    if wood:
        p.inventory.append(create_item("logs", wood))
    if stone:
        p.inventory.append(create_item("stone", stone))


class TestClaim(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_buy_a_derelict(self):
        loc, _ = _enter_derelict(self.engine)
        _stock(self.engine)
        gold0 = self.p.gold
        msg = homestead.claim(self.engine)
        self.assertIn("buy", msg.lower())
        self.assertTrue(homestead.owns_home(self.p))
        self.assertEqual(homestead.home_name(self.p), loc.name)
        self.assertEqual(loc.get_property("owner"), "player")
        self.assertFalse(homestead.is_ready(self.p))
        self.assertLess(self.p.gold, gold0)      # it cost something

    def test_cannot_afford(self):
        loc, _ = _enter_derelict(self.engine)
        self.p.gold = 5
        msg = homestead.claim(self.engine)
        self.assertIn("short", msg.lower())
        self.assertFalse(homestead.owns_home(self.p))
        self.assertIsNone(loc.get_property("owner"))

    def test_only_unowned_derelicts_are_claimable(self):
        loc, _ = _enter_derelict(self.engine)
        loc.add_property("derelict", False)      # a lived-in building
        self.assertIsNone(homestead.claimable_here(self.engine))
        loc.add_property("derelict", True)
        loc.add_property("owner", "someone")     # already spoken for
        self.assertIsNone(homestead.claimable_here(self.engine))

    def test_one_home_at_a_time(self):
        _enter_derelict(self.engine, name="Shack A")
        _stock(self.engine)
        homestead.claim(self.engine)
        loc_b, _ = _enter_derelict(self.engine, name="Shack B")
        msg = homestead.claim(self.engine)
        self.assertIn("already", msg.lower())
        self.assertIsNone(loc_b.get_property("owner"))


class TestRepair(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.loc, self.inter = _enter_derelict(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_repair_to_completion_furnishes_and_clears_derelict(self):
        _stock(self.engine)
        homestead.claim(self.engine)
        for i in range(homestead.REPAIR_STAGES):
            msg = homestead.repair(self.engine)
            self.assertIsNotNone(msg)
        self.assertTrue(homestead.is_ready(self.p))
        self.assertFalse(self.loc.get_property("derelict"))
        kinds = {_kind(pc["name"]) for pc in self.inter.furniture}
        self.assertIn("bed", kinds)
        self.assertIn("hearth", kinds)
        self.assertIn("stash", kinds)

    def test_repair_needs_materials(self):
        _stock(self.engine, wood=0, stone=0)      # gold only
        homestead.claim(self.engine)
        msg = homestead.repair(self.engine)
        self.assertIn("need", msg.lower())
        proj = self.p.metadata["home_project"]
        self.assertEqual(proj["stage"], 0)         # no progress

    def test_repair_consumes_wood_stone_gold(self):
        _stock(self.engine, wood=3, stone=2, gold=300)
        homestead.claim(self.engine)
        g0 = self.p.gold
        homestead.repair(self.engine)
        self.assertEqual(homestead._count(self.p, homestead.WOOD_IDS), 0)
        self.assertEqual(homestead._count(self.p, homestead.STONE_IDS), 0)
        self.assertEqual(self.p.gold, g0 - homestead.STAGE_GOLD)

    def test_home_action_claims_then_repairs(self):
        _stock(self.engine)
        self.assertIn("buy", homestead.home_action(self.engine).lower())
        self.assertTrue(homestead.owns_home(self.p))
        # second E now repairs (owned, unfinished)
        msg = homestead.home_action(self.engine)
        self.assertIn("shore up", msg.lower())


class TestLiveInIt(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.loc, self.inter = _enter_derelict(self.engine)
        _stock(self.engine)
        homestead.claim(self.engine)
        for _ in range(homestead.REPAIR_STAGES):
            homestead.repair(self.engine)
        assert homestead.is_ready(self.p)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_rest_at_home_is_free(self):
        from engine.rest import can_sleep_here, sleep
        self.assertTrue(homestead.can_rest_home(self.engine))
        self.assertIsNone(can_sleep_here(self.engine))
        self.p.gold = 0                     # broke — but you own the bed
        lines = sleep(self.engine)
        self.assertTrue(lines)              # it did NOT refuse
        self.assertEqual(self.p.gold, 0)    # and cost nothing

    def test_store_and_take_from_the_chest(self):
        herbs = create_item("herb_bundle")       # not in the starting kit
        self.p.inventory.append(herbs)
        msg = homestead.deposit(self.engine, herbs.name)
        self.assertIn("stored", msg.lower())
        self.assertNotIn(herbs, self.p.inventory)
        self.assertIn(herbs.name, homestead.stored_names(self.p))
        # E on the chest takes the top item back
        back = homestead.chest_interact(self.engine)
        self.assertIn("take", back.lower())
        self.assertTrue(any(getattr(i, "id", "") == "herb_bundle"
                            for i in self.p.inventory))

    def test_empty_chest_message(self):
        self.assertIn("empty", homestead.chest_interact(self.engine).lower())

    def test_storage_survives_save_load(self):
        herbs = create_item("herb_bundle")
        self.p.inventory.append(herbs)
        homestead.deposit(self.engine, herbs.name)
        # the stored payload is plain JSON -> save-safe
        json.dumps(self.p.metadata["home_storage"])
        self.engine.save_game(name="p157_roundtrip")
        e2 = GameEngine(llm_provider="heuristic",
                        enable_npc_processes=False)
        e2.start_game()
        self.assertTrue(e2.load_game(name="p157_roundtrip"))
        self.assertIn(herbs.name, homestead.stored_names(e2.player))
        homestead.withdraw(e2, herbs.name)     # usable after reload
        self.assertTrue(any(getattr(i, "id", "") == "herb_bundle"
                            for i in e2.player.inventory))
        e2.end_game()


if __name__ == "__main__":
    unittest.main()
