"""Tests for spells + mana."""

import unittest

from engine.game_engine import GameEngine
from engine.spells import (
    SPELL_REGISTRY, ensure_mana, get_mana, get_known_spells,
    starting_spells_for, rest_recover_mana,
)


class TestSpellRegistry(unittest.TestCase):
    def test_known_spells(self):
        ids = list(SPELL_REGISTRY.keys())
        for needed in ("magic_missile", "fireball", "heal", "bless"):
            self.assertIn(needed, ids)

    def test_starting_spells_by_class(self):
        wizard_spells = starting_spells_for("wizard")
        self.assertTrue(wizard_spells)
        cleric_spells = starting_spells_for("cleric")
        self.assertTrue(any(s.id == "heal" for s in cleric_spells))
        villager_spells = starting_spells_for("villager")
        self.assertFalse(villager_spells)


class TestSpellsInEngine(unittest.TestCase):
    def setUp(self):
        # Wizard player to get spells
        from ui.character_creator import CharacterSpec
        from characters.character_types import CharacterClass, CharacterRace
        spec = CharacterSpec(
            name="Mage",
            race=CharacterRace.HUMAN,
            character_class=CharacterClass.WIZARD,
            stats={"strength": 8, "dexterity": 12, "constitution": 10,
                   "intelligence": 16, "wisdom": 12, "charisma": 10},
        )
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False,
            player_spec=spec,
        )
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_wizard_starts_with_mana(self):
        mana, max_mana = self.engine.get_player_mana()
        self.assertGreater(max_mana, 0)
        self.assertEqual(mana, max_mana)

    def test_wizard_knows_spells(self):
        spells = self.engine.get_player_spells()
        self.assertTrue(spells)
        self.assertTrue(any(s.id == "magic_missile" for s in spells))

    def test_cast_costs_mana(self):
        before, _ = self.engine.get_player_mana()
        # Cast magic missile (no target needed — picks nearest hostile)
        # Move troll close so it's in range
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(troll)
        troll.position = (self.engine.player.position[0] + 3,
                          self.engine.player.position[1])
        self.engine.world.map.place_character(troll, *troll.position)
        msg = self.engine.cast_spell("magic_missile")
        self.assertTrue(msg)
        after, _ = self.engine.get_player_mana()
        self.assertLess(after, before)

    def test_cast_unknown_spell(self):
        msg = self.engine.cast_spell("nonsense_spell")
        self.assertIn("unknown", msg.lower())

    def test_cast_no_mana(self):
        # Initialize mana first (so ensure_mana doesn't overwrite), then drain
        ensure_mana(self.engine.player)
        self.engine.player.metadata["mana"] = 0
        msg = self.engine.cast_spell("fireball")
        self.assertIn("mana", msg.lower())

    def test_rest_recovers_mana(self):
        ensure_mana(self.engine.player)
        self.engine.player.metadata["mana"] = 0
        rest_recover_mana(self.engine.player, amount=5)
        self.assertEqual(self.engine.player.metadata["mana"], 5)


if __name__ == "__main__":
    unittest.main()
