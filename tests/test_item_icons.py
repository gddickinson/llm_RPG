"""Richer, type + rarity-aware item ICONS (replacing the flat glyph)."""

import unittest

import pygame

from ui import item_icons as ic


class TestClassify(unittest.TestCase):
    def test_keyword_wins(self):
        self.assertEqual(ic._classify("misc", "Iron Sword"), "sword")
        self.assertEqual(ic._classify("misc", "Hunting Bow"), "bow")
        self.assertEqual(ic._classify("weapon", "Battleaxe"), "axe")
        self.assertEqual(ic._classify("consumable", "Healing Potion"),
                         "flask")
        self.assertEqual(ic._classify("misc", "Ruby"), "gem")
        self.assertEqual(ic._classify("misc", "Ancient Tome"), "book")
        self.assertEqual(ic._classify("ring", "Ring of Power"), "ring")

    def test_type_fallback(self):
        # an odd name falls back to the item TYPE's archetype
        self.assertEqual(ic._classify("armor", "Xyzzy Vest"), "breastplate")
        self.assertEqual(ic._classify("currency", "42 gold"), "coins")
        self.assertEqual(ic._classify("misc", "Whatsit"), "crate")


class TestRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))

    def test_every_archetype_renders(self):
        for arch in ic._DRAW:
            for rar in ("common", "rare", "legendary"):
                spr = ic._cached(arch, rar, 48)
                self.assertIsInstance(spr, pygame.Surface)
                self.assertEqual(spr.get_size(), (48, 48))

    def test_icon_from_item(self):
        from items.item_registry import create_item
        for iid in ("sword", "greater_potion", "chainmail",
                    "staff_of_the_magi", "ring_of_regeneration"):
            it = create_item(iid)
            if it is None:
                continue
            spr = ic.icon(it, 40)
            self.assertEqual(spr.get_size(), (40, 40))

    def test_icon_by_name(self):
        spr = ic.icon_by_name("Wolf Pelt", 32)
        self.assertEqual(spr.get_size(), (32, 32))

    def test_sprite_loader_uses_rich_icons(self):
        from ui.sprite_loader import SpriteLoader
        sl = SpriteLoader(tile_size=48)
        spr = sl.item("Iron Sword")
        self.assertIsInstance(spr, pygame.Surface)


if __name__ == "__main__":
    unittest.main()
