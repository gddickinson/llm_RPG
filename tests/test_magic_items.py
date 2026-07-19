"""A large range of magical objects (George): charged wands/staves that cast
spells, one-shot scrolls, enchanted + legendary gear across every category.
"""

import unittest

from items.item_registry import create_item, ITEM_REGISTRY
from engine.spells import SPELL_REGISTRY


class TestCatalogue(unittest.TestCase):
    def test_new_items_load(self):
        for iid in ("wand_of_firebolts", "staff_of_the_magi", "sunblade",
                    "ring_of_three_wishes", "scroll_lightning_bolt",
                    "robe_of_the_magi", "orb_of_dragonkind",
                    "book_of_infinite_spells", "gauntlets_of_ogre_power"):
            self.assertIsNotNone(create_item(iid), iid)

    def test_a_large_range_exists(self):
        self.assertGreater(len(ITEM_REGISTRY), 200)

    def test_every_spell_item_references_a_real_spell(self):
        for iid, item in ITEM_REGISTRY.items():
            sid = (item.use_effect or {}).get("spell")
            if sid:
                self.assertIn(sid, SPELL_REGISTRY, f"{iid} casts unknown {sid}")

    def test_legendaries_are_powerful(self):
        for iid in ("staff_of_the_magi", "sunblade", "ring_of_the_archmage"):
            it = create_item(iid)
            self.assertEqual(it.rarity.value, "legendary")
            self.assertTrue(it.equip_bonuses or it.use_effect,
                            f"{iid} should DO something")


class TestChargedItems(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        from ui.character_creator import CharacterSpec
        from characters.character_types import CharacterClass, CharacterRace
        spec = CharacterSpec(name="Mage", race=CharacterRace.HUMAN,
                             character_class=CharacterClass.WIZARD,
                             stats={"strength": 8, "dexterity": 10,
                                    "constitution": 10, "intelligence": 16,
                                    "wisdom": 12, "charisma": 10})
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False, player_spec=spec)
        self.engine.start_game()
        self.p = self.engine.player
        self.p.metadata["mana"] = 200

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _has(self, iid):
        return any(getattr(x, "id", "") == iid for x in self.p.inventory)

    def test_wand_uses_charges_then_crumbles(self):
        from engine.item_use import use_item
        wand = create_item("wand_of_firebolts")
        start = wand.metadata["charges"]
        self.p.add_item(wand)
        use_item(self.engine, "Wand of Firebolts")
        self.assertEqual(wand.metadata["charges"], start - 1)
        self.assertTrue(self._has("wand_of_firebolts"), "still has charges")
        # burn it down
        for _ in range(start):
            use_item(self.engine, "Wand of Firebolts")
        self.assertFalse(self._has("wand_of_firebolts"), "spent → crumbles")

    def test_scroll_is_one_shot(self):
        from engine.item_use import use_item
        self.p.add_item(create_item("scroll_ice_shard"))
        use_item(self.engine, "Scroll of Ice Shard")
        self.assertFalse(self._has("scroll_ice_shard"), "a scroll burns away")

    def test_charged_item_persists_charges(self):
        import tempfile
        import os
        wand = create_item("wand_of_frost")
        self.p.add_item(wand)
        from engine.item_use import use_item
        use_item(self.engine, "Wand of Frost")
        left = wand.metadata["charges"]
        path = os.path.join(tempfile.mkdtemp(), "w.json")
        self.engine.save_game(path)
        from engine.game_engine import GameEngine
        eng2 = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng2.load_game(path)
        w2 = next((x for x in eng2.player.inventory
                   if getattr(x, "id", "") == "wand_of_frost"), None)
        self.assertIsNotNone(w2)
        self.assertEqual(w2.metadata.get("charges"), left)
        try:
            eng2.end_game()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
