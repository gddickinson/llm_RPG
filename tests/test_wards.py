"""Magical protection by power (George): a magically-shaped tile / enchanted item
can only be altered by a caster AT LEAST AS POWERFUL as its creator; mundane
labour can't touch a magic ward at all.
"""

import unittest

from engine.game_engine import GameEngine
from engine import worldcraft as wc
from engine.wards import WardSystem, caster_power
from world.world_map import TerrainType
from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from items.item_registry import create_item


def _caster(name, level, intel=16):
    return Character(id=name, name=name, character_class=CharacterClass.WIZARD,
                     race=CharacterRace.HUMAN, level=level, strength=8,
                     dexterity=10, constitution=10, intelligence=intel,
                     wisdom=12, charisma=10, hp=20, max_hp=20, position=(15, 5),
                     metadata={})


class TestCasterPower(unittest.TestCase):
    def test_level_and_int_drive_power(self):
        self.assertLess(caster_power(_caster("a", 3, 10)),
                        caster_power(_caster("b", 12, 18)))

    def test_int_bonus(self):
        self.assertGreater(caster_power(_caster("smart", 5, 18)),
                           caster_power(_caster("dim", 5, 10)))


class TestWardSystem(unittest.TestCase):
    def test_set_get_clear_and_roundtrip(self):
        w = WardSystem(None)
        w.set(3, 4, 15)
        self.assertEqual(w.power_at(3, 4), 15)
        self.assertEqual(w.power_at(0, 0), 0)
        w.set(3, 4, 0)                     # 0 clears
        self.assertEqual(w.power_at(3, 4), 0)
        w.set(1, 1, 8)
        w2 = WardSystem(None)
        w2.from_dict(w.to_dict())
        self.assertEqual(w2.power_at(1, 1), 8)


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _grass(self):
        for y in range(self.wmap.height):
            for x in range(self.wmap.width):
                if self.wmap.get_terrain_at(x, y) == TerrainType.GRASS \
                        and not wc.protected(self.engine, x, y) \
                        and (x, y) not in self.wmap.characters:
                    return x, y
        self.skipTest("no free grass")


class TestTerrainWards(_Base):
    def test_magic_stamps_a_ward(self):
        strong = _caster("Archmage", 12)
        x, y = self._grass()
        wc.mutate(self.engine, x, y, "building", "magic", actor=strong)
        self.assertEqual(self.engine.wards.power_at(x, y),
                         caster_power(strong))

    def test_weaker_caster_cannot_alter(self):
        strong, weak = _caster("Archmage", 12), _caster("Hedge", 3)
        x, y = self._grass()
        wc.mutate(self.engine, x, y, "building", "magic", actor=strong)
        ok, why = wc.can_mutate(self.engine, x, y, "rubble", "magic",
                                actor=weak)
        self.assertFalse(ok)
        self.assertIn("greater power", why)

    def test_labour_cannot_touch_a_ward(self):
        strong = _caster("Archmage", 12)
        x, y = self._grass()
        wc.mutate(self.engine, x, y, "building", "magic", actor=strong)
        ok, why = wc.can_mutate(self.engine, x, y, "rubble", "labor",
                                actor=strong)   # even a strong LABOURER can't
        self.assertFalse(ok)
        self.assertIn("mundane", why)

    def test_equal_or_greater_caster_can(self):
        strong = _caster("Archmage", 12)
        x, y = self._grass()
        wc.mutate(self.engine, x, y, "building", "magic", actor=strong)
        ok, _ = wc.can_mutate(self.engine, x, y, "rubble", "magic",
                              actor=strong)
        self.assertTrue(ok)

    def test_ward_persists_save_load(self):
        import tempfile
        import os
        strong = _caster("Archmage", 12)
        x, y = self._grass()
        wc.mutate(self.engine, x, y, "building", "magic", actor=strong)
        path = os.path.join(tempfile.mkdtemp(), "w.json")
        self.engine.save_game(path)
        eng2 = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng2.load_game(path)
        self.assertEqual(eng2.wards.power_at(x, y), caster_power(strong))
        try:
            eng2.end_game()
        except Exception:
            pass


class TestEnchantWard(_Base):
    def _forge(self):
        forge = next((l for l in self.engine.world.locations
                      if (l.properties or {}).get("forge")), None)
        if forge is None:
            self.skipTest("no forge")
        self.engine.player.position = forge.center()

    def test_weaker_enchanter_cannot_rework(self):
        from items import enchanting as en
        from engine.skill_progression import add_skill_xp, total_xp_for_level
        self._forge()
        p = self.engine.player
        p.add_item(create_item("arcane_dust", quantity=8))
        p.add_item(create_item("ember_core", quantity=2))
        add_skill_xp(p, "enchanting", total_xp_for_level(6))
        sword = create_item("sword")
        p.add_item(sword)
        p.level, p.intelligence = 12, 16          # a mighty enchanter
        ok, _ = en.enchant(self.engine, sword, "flametongue")
        self.assertTrue(ok)
        self.assertGreater(sword.metadata.get("ward_power", 0), 0)
        p.level, p.intelligence = 2, 10           # now a weak one
        ok, why = en.can_enchant(self.engine, sword, "keen_edge")
        self.assertFalse(ok)
        self.assertIn("mightier", why)


if __name__ == "__main__":
    unittest.main()
