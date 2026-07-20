"""Shapeshifting (George): willing forms (wild shape, a totem) and forms
forced on you (baleful polymorph, a cursed stone) — with the beast's
natural attacks, its restrictions, and the routes back."""

import unittest

from engine.game_engine import GameEngine
from engine import shapeshift as ss
from ui.character_creator import CharacterSpec
from characters.character_types import CharacterClass, CharacterRace
from items.item_registry import create_item


def _engine(cls=CharacterClass.DRUID):
    spec = CharacterSpec(name="Fenn", race=CharacterRace.HUMAN,
                         character_class=cls,
                         stats={"strength": 12, "dexterity": 12,
                                "constitution": 12, "intelligence": 12,
                                "wisdom": 14, "charisma": 10})
    e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                   player_spec=spec)
    e.start_game()
    return e


class TestShiftRevert(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_shift_sets_form_render_and_combat(self):
        base_max = self.p.max_hp
        ss.shift(self.engine, self.p, "wolf")
        self.assertTrue(ss.is_shifted(self.p))
        self.assertEqual(self.p.metadata["body_plan"], "quadruped")
        self.assertEqual(self.p.metadata["model"], "wolf")
        self.assertEqual(self.p.metadata["natural_damage"], 6)
        self.assertGreater(self.p.max_hp, base_max)            # 1.2x
        self.assertTrue(ss.restricted(self.p, "no_wield"))

    def test_revert_restores(self):
        base_max = self.p.max_hp
        ss.shift(self.engine, self.p, "wolf")
        ss.revert(self.engine, self.p)
        self.assertFalse(ss.is_shifted(self.p))
        self.assertNotIn("shapeshift", self.p.metadata)
        self.assertNotIn("body_plan", self.p.metadata)
        self.assertEqual(self.p.max_hp, base_max)

    def test_hp_fraction_preserved(self):
        self.p.hp = self.p.max_hp
        ss.shift(self.engine, self.p, "frog")                  # 0.25x
        self.assertLess(self.p.max_hp, 20)
        # take half the frog's hp, then revert
        self.p.hp = max(1, self.p.max_hp // 2)
        ss.revert(self.engine, self.p, force=True)
        self.assertLessEqual(self.p.hp, self.p.max_hp)
        self.assertGreater(self.p.hp, 0)

    def test_involuntary_cannot_self_revert_but_cure_can(self):
        ss.shift(self.engine, self.p, "toad", involuntary=True)
        msg = ss.revert(self.engine, self.p)                   # no force
        self.assertIn("forced", msg.lower())
        self.assertTrue(ss.is_shifted(self.p))
        ss.remove_curse(self.engine, self.p)                   # the cure
        self.assertFalse(ss.is_shifted(self.p))

    def test_timed_form_reverts_on_tick(self):
        ss.shift(self.engine, self.p, "wolf", duration=2)
        ss.tick(self.engine)
        self.assertTrue(ss.is_shifted(self.p))
        ss.tick(self.engine)
        self.assertFalse(ss.is_shifted(self.p))


class TestCombatAndCast(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_beast_fights_with_natural_attacks(self):
        sword = create_item("sword")
        self.p.inventory.append(sword)
        from characters import equipment as eqp
        eqp.equip(self.p, sword)
        ss.shift(self.engine, self.p, "bear")                  # natural 9
        dmg = self.engine.combat_system._best_weapon_damage(self.p)
        self.assertEqual(dmg, 9)                               # claws, not blade

    def test_no_cast_blocks_ordinary_spells(self):
        self.p.metadata["spells_known"] = ["heal", "wild_shape"]
        self.p.metadata["mana"] = 50
        ss.shift(self.engine, self.p, "wolf")                  # no_cast
        msg = self.engine.cast_spell("heal")
        self.assertIn("shape", msg.lower())
        self.assertGreater(self.p.hp, 0)

    def test_wild_shape_spell_toggles(self):
        self.p.metadata["spells_known"] = ["wild_shape"]
        self.p.metadata["mana"] = 50
        self.engine.cast_spell("wild_shape")
        self.assertTrue(ss.is_shifted(self.p))
        self.engine.cast_spell("wild_shape")                   # cast again = revert
        self.assertFalse(ss.is_shifted(self.p))


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.engine = _engine(CharacterClass.WIZARD)
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_cursed_item_transforms_involuntarily(self):
        stone = create_item("cursed_toadstone")
        self.p.add_item(stone)
        from engine.item_use import use_item
        use_item(self.engine, "Cursed Toadstone")
        self.assertEqual(ss.current_form(self.p), "toad")
        # can't shrug it off — it's a curse
        self.assertIn("forced", ss.revert(self.engine, self.p).lower())

    def test_cure_item_lifts_a_curse(self):
        ss.shift(self.engine, self.p, "frog", involuntary=True)
        elixir = create_item("restoration_elixir")
        self.p.add_item(elixir)
        from engine.item_use import use_item
        use_item(self.engine, "Elixir of Restoration")
        self.assertFalse(ss.is_shifted(self.p))

    def test_totem_gives_a_non_caster_a_form(self):
        totem = create_item("beastlord_totem")
        self.p.add_item(totem)
        from engine.item_use import use_item
        use_item(self.engine, "Beastlord's Totem")
        self.assertEqual(ss.current_form(self.p), "wolf")
        # a totem is reusable — not consumed
        self.assertTrue(any(getattr(i, "id", "") == "beastlord_totem"
                            for i in self.p.inventory))

    def test_baleful_polymorph_on_a_foe(self):
        from world.monsters import build_monster
        goblin = build_monster("goblin", (self.p.position[0] + 1,
                                           self.p.position[1]))
        goblin.id = "shift_goblin"
        self.engine.npc_manager.add_npc(goblin)
        self.p.metadata["spells_known"] = ["baleful_polymorph"]
        self.p.metadata["mana"] = 50
        self.engine.cast_spell("baleful_polymorph", "Goblin")
        self.assertEqual(ss.current_form(goblin), "toad")
        self.assertTrue(ss.restricted(goblin, "no_wield"))


if __name__ == "__main__":
    unittest.main()
