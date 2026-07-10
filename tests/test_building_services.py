"""Building-service tests (P9A.6) — bank at the temple, repair at
the forge, all interior-aware."""

import unittest

from engine.game_engine import GameEngine
from engine.furniture import interact
from items.item_registry import create_item


class TestBuildingServices(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.engine.world.time = 12 * 60

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _inside(self, fragment):
        interior = next(i for name, i in self.engine.interiors.items()
                        if fragment in name.lower())
        self.engine.current_interior = interior
        self.player.position = interior.door
        return interior

    def test_player_location_is_interior_aware(self):
        self._inside("temple")
        loc = self.engine.player_location()
        self.assertIsNotNone(loc)
        self.assertIn("temple", loc.name.lower())

    def test_player_location_works_from_a_loft(self):
        tavern = self._inside("tavern")
        self.engine.current_interior = tavern.level_above
        loc = self.engine.player_location()
        self.assertIn("tavern", loc.name.lower())

    def test_banking_works_inside_the_temple(self):
        self._inside("temple")
        self.player.gold = 50
        msg = self.engine.deposit_gold(30)
        self.assertIn("deposit", msg.lower())
        self.assertEqual(self.engine.bank_balance(), 30)
        self.assertEqual(self.player.gold, 20)

    def test_banking_refused_in_a_farmhouse(self):
        self._inside("farmhouse")
        self.player.gold = 50
        msg = self.engine.deposit_gold(10)
        self.assertIn("only deposit", msg.lower())

    def test_forge_crafting_works_inside_the_forge(self):
        self._inside("durgan")
        loc = self.engine.player_location()
        self.assertIsNotNone(loc)
        # the location property gate sees the forge from indoors
        from items.crafting import RECIPES
        gated = [r for r in RECIPES.values()
                 if r.required_property == "forge"]
        if not gated:
            self.skipTest("no forge-gated recipes")
        # No ingredients: the craft must fail on ingredients, not on
        # "you need a forge"
        msg = self.engine.craft(gated[0].output_id)
        self.assertNotIn("forge", msg.lower().split("need")[-1][:20])

    def test_anvil_repairs_damaged_gear(self):
        from engine.durability import get_durability, max_durability
        from characters.equipment import equip
        self._inside("durgan")
        interior = self.engine.current_interior
        anvil = next(f for f in interior.furniture
                     if f["name"] == "Anvil")
        self.player.position = (anvil["x"], anvil["y"])
        sword = create_item("longsword")
        sword.metadata = getattr(sword, "metadata", {}) or {}
        from engine.durability import degrade, is_degradable
        if not is_degradable(sword):
            self.skipTest("longsword not degradable")
        for _ in range(10):
            degrade(sword)
        self.player.inventory.append(sword)
        self.player.gold = 500
        msg = interact(self.engine)
        self.assertIn("repair", msg.lower())
        self.assertEqual(get_durability(sword),
                         max_durability(sword))

    def test_anvil_with_pristine_gear_teaches(self):
        self._inside("durgan")
        interior = self.engine.current_interior
        anvil = next(f for f in interior.furniture
                     if f["name"] == "Anvil")
        self.player.position = (anvil["x"], anvil["y"])
        msg = interact(self.engine)
        self.assertIn("good order", msg)

    def test_the_village_well_quenches(self):
        wells = [i for name, i in self.engine.interiors.items()
                 if "well" in name.lower()]
        if not wells:
            self.skipTest("no well this world")
        self.engine.current_interior = wells[0]
        well = next(f for f in wells[0].furniture
                    if f["name"] == "Well")
        self.player.position = (well["x"], well["y"])
        self.player.hp = self.player.max_hp - 4
        msg = interact(self.engine)
        self.assertIn("drink", msg.lower())
        msg = interact(self.engine)
        self.assertIn("had your fill", msg)

    def test_bank_hint_inside_temple(self):
        from ui.hints import context_hints
        self._inside("temple")
        hints = " ".join(context_hints(self.engine))
        self.assertIn("[N] deposit", hints)


if __name__ == "__main__":
    unittest.main()
