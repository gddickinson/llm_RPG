"""Pet loyalty tests (P12.14): tameness, treats, neglect, fetch."""

import unittest

from engine.game_engine import GameEngine
from engine.pets import FETCH_AT, TAME_MAX, TAME_START
from items.item_registry import create_item


class TestPetLoyalty(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.pets = self.engine.pet_system
        self.meta = self.player.metadata
        # adopt Rocky directly
        self.meta["pets"] = ["mining"]
        self.meta["active_pet"] = "mining"
        self.meta["pet_tameness"] = {"mining": TAME_START}

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_a_treat_deepens_the_bond(self):
        self.player.inventory = [create_item("bread")]
        msg = self.pets.feed_pet()
        self.assertIn("loyalty 11", msg)
        self.assertEqual(self.player.inventory, [],
                         "the treat is eaten")
        self.assertEqual(self.meta["pet_fed_day"],
                         self.engine.world.time // (24 * 60))

    def test_loyalty_caps_at_twenty(self):
        self.meta["pet_tameness"]["mining"] = TAME_MAX
        self.player.inventory = [create_item("bread")]
        self.pets.feed_pet()
        self.assertEqual(self.pets.tameness(), TAME_MAX)

    def test_no_food_no_treat(self):
        self.player.inventory = []
        msg = self.pets.feed_pet()
        self.assertIn("empty hands", msg)
        self.assertEqual(self.pets.tameness(), TAME_START)

    def test_neglect_wears_the_bond(self):
        self.pets.run_night()
        self.assertEqual(self.pets.tameness(), TAME_START - 1)

    def test_a_fed_pet_holds_steady(self):
        day = self.engine.world.time // (24 * 60)
        self.meta["pet_fed_day"] = day - 1     # fed yesterday
        self.pets.run_night()
        self.assertEqual(self.pets.tameness(), TAME_START)

    def test_at_zero_they_walk_away(self):
        self.meta["pet_tameness"]["mining"] = 1
        self.pets.run_night()
        self.assertNotIn("mining", self.meta["pets"],
                         "gone from the collection")
        self.assertIsNone(self.meta["active_pet"])
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("gone come morning", log)

    def _clean_corner(self):
        """A staging spot with no worldgen ground litter in range."""
        wmap = self.engine.world.map
        ox, oy = wmap.width - 8, wmap.height - 6
        for y in range(oy - 4, oy + 5):
            for x in range(ox - 4, ox + 5):
                for it in list(self.engine.world.get_items_at(x, y)):
                    try:
                        self.engine.world.remove_item_from_ground(
                            it, x, y)
                    except Exception:
                        pass
        self.player.position = (ox, oy)
        return ox, oy

    def test_a_loyal_pet_fetches(self):
        self.meta["pet_tameness"]["mining"] = FETCH_AT
        px, py = self._clean_corner()
        self.pets.follow_pos = (px, py)
        loot = create_item("ale")
        self.engine.world.add_item_to_ground(loot, px + 1, py)
        self.pets.rng.random = lambda: 0.0     # the dart happens
        msg = self.pets.maybe_fetch()
        self.assertIsNotNone(msg)
        self.assertIn("darts off", msg)
        self.assertIn(loot, self.player.inventory)

    def test_an_aloof_pet_does_not(self):
        self.meta["pet_tameness"]["mining"] = FETCH_AT - 1
        px, py = self._clean_corner()
        self.pets.follow_pos = (px, py)
        self.engine.world.add_item_to_ground(
            create_item("ale"), px + 1, py)
        self.pets.rng.random = lambda: 0.0
        self.assertIsNone(self.pets.maybe_fetch(),
                          "apport is trained, not given")

    def test_new_pets_start_at_ten(self):
        self.meta["pets"] = []
        self.meta["active_pet"] = None
        self.meta["pet_tameness"] = {}
        self.pets.rng.randint = lambda a, b: 1     # jackpot roll
        self.pets.maybe_award("foraging")
        self.assertEqual(self.pets.tameness("foraging"), TAME_START)


if __name__ == "__main__":
    unittest.main()
