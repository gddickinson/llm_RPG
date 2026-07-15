"""P25.1 — stackable items group into one slot (arrows/ammo/potions/raws)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_stack_"))

import unittest

from items.item_registry import create_item
from items.item import Item
from items.inventory_ops import can_stack, find_stack, stack_add
from engine.law import mark_stolen


class TestStackHelpers(unittest.TestCase):
    def test_identical_stackables_merge(self):
        inv = []
        self.assertFalse(stack_add(inv, create_item("arrow", quantity=10)))
        self.assertTrue(stack_add(inv, create_item("arrow", quantity=15)))
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0].quantity, 25)

    def test_non_stackable_never_merges(self):
        inv = []
        stack_add(inv, create_item("sword"))
        stack_add(inv, create_item("sword"))
        self.assertEqual(len(inv), 2)

    def test_stolen_goods_stay_distinct(self):
        inv = [create_item("arrow", quantity=5)]
        stolen = create_item("arrow", quantity=3)
        mark_stolen(stolen)
        self.assertFalse(can_stack(inv[0], stolen))
        stack_add(inv, stolen)
        self.assertEqual(len(inv), 2, "a stolen stack keeps its own slot")

    def test_metadata_difference_stays_distinct(self):
        a = create_item("arrow", quantity=2)
        b = create_item("arrow", quantity=2)
        b.metadata = {"rune": "flame"}
        self.assertFalse(can_stack(a, b))
        self.assertIsNone(find_stack([a], b))

    def test_find_stack_only_for_stackables(self):
        inv = [create_item("arrow", quantity=1)]
        self.assertIsNotNone(find_stack(inv, create_item("arrow")))
        self.assertIsNone(find_stack(inv, create_item("sword")))


class TestCharacterAddItem(unittest.TestCase):
    def _hero(self):
        from characters.character import Character
        from characters.character_types import CharacterClass, CharacterRace
        return Character(
            id="h", name="H", character_class=CharacterClass.WARRIOR,
            race=CharacterRace.HUMAN, level=1, strength=12, dexterity=12,
            constitution=12, intelligence=10, wisdom=10, charisma=10,
            hp=20, max_hp=20)

    def test_add_item_stacks_and_reports_merge(self):
        h = self._hero()
        self.assertFalse(h.add_item(create_item("arrow", quantity=3)))
        self.assertTrue(h.add_item(create_item("arrow", quantity=4)))
        self.assertEqual(len(h.inventory), 1)
        self.assertEqual(h.inventory[0].quantity, 7)

    def test_stack_is_one_carry_slot(self):
        from engine.carry import used_slots
        h = self._hero()
        h.add_item(create_item("arrow", quantity=40))
        self.assertEqual(used_slots(h), 1, "a 40-arrow stack is one slot")

    def test_display_shows_the_count(self):
        h = self._hero()
        h.add_item(create_item("arrow", quantity=12))
        self.assertIn("x12", str(h.inventory[0]))


class TestSaveRoundTrip(unittest.TestCase):
    def test_quantity_survives_serialisation(self):
        it = create_item("arrow", quantity=17)
        back = Item.from_dict(it.to_dict())
        self.assertTrue(back.stackable)
        self.assertEqual(back.quantity, 17)


class TestPickupStacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_pickup_merges_into_existing_stack(self):
        eng = self.engine
        p = eng.player
        p.inventory = [create_item("arrow", quantity=5)]
        x, y = p.position
        eng.world.add_item_to_ground(create_item("arrow", quantity=8), x, y)
        msg = eng.pickup_item()
        self.assertEqual(len(p.inventory), 1, f"should merge, not add: {msg}")
        self.assertEqual(p.inventory[0].quantity, 13)

    def test_full_pack_can_still_top_up_a_stack(self):
        from engine.carry import capacity, can_carry
        eng = self.engine
        p = eng.player
        # fill the pack to capacity with distinct non-stackables + one stack
        p.inventory = [create_item("arrow", quantity=2)]
        i = 0
        while can_carry(p):
            sw = create_item("sword")
            sw.id = f"junk_{i}"          # distinct so they never stack
            p.inventory.append(sw)
            i += 1
        self.assertFalse(can_carry(p), "pack should be full now")
        x, y = p.position
        eng.world.add_item_to_ground(create_item("arrow", quantity=6), x, y)
        before = len(p.inventory)
        eng.pickup_item()
        self.assertEqual(len(p.inventory), before, "no new slot on a merge")
        stack = next(it for it in p.inventory
                     if getattr(it, "id", "") == "arrow")
        self.assertEqual(stack.quantity, 8, "the stack topped up despite a full pack")


if __name__ == "__main__":
    unittest.main()
