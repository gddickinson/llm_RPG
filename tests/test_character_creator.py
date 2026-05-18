"""Tests for the character creator data flow (no pygame UI)."""

import random
import unittest

from characters.character_types import CharacterClass, CharacterRace
from ui.character_creator import (
    CharacterSpec, default_quick_start_spec,
    RACE_BONUSES, CLASS_STARTERS, PLAYER_RACES, PLAYER_CLASSES,
    roll_stats, apply_race_bonus,
)


class TestCharacterCreator(unittest.TestCase):
    def test_quick_start_spec(self):
        spec = default_quick_start_spec()
        self.assertIsInstance(spec, CharacterSpec)
        self.assertEqual(spec.race, CharacterRace.HUMAN)
        self.assertEqual(spec.character_class, CharacterClass.WARRIOR)
        # All stats present
        for stat in ("strength", "dexterity", "constitution",
                     "intelligence", "wisdom", "charisma"):
            self.assertIn(stat, spec.stats)

    def test_roll_stats_range(self):
        rng = random.Random(1)
        stats = roll_stats(rng)
        for v in stats.values():
            # 4d6 drop lowest: min 3, max 18
            self.assertGreaterEqual(v, 3)
            self.assertLessEqual(v, 18)

    def test_race_bonus_applied(self):
        base = {"strength": 10, "dexterity": 10, "constitution": 10,
                "intelligence": 10, "wisdom": 10, "charisma": 10}
        adjusted = apply_race_bonus(base, CharacterRace.ELF)
        self.assertEqual(adjusted["dexterity"], 12)  # +2 from elf

    def test_player_race_list(self):
        # Player options exclude troll
        self.assertNotIn(CharacterRace.TROLL, PLAYER_RACES)
        self.assertIn(CharacterRace.HUMAN, PLAYER_RACES)

    def test_player_class_list(self):
        # Hostile classes not in player picker
        self.assertNotIn(CharacterClass.BRIGAND, PLAYER_CLASSES)
        self.assertNotIn(CharacterClass.MONSTER, PLAYER_CLASSES)
        self.assertIn(CharacterClass.WIZARD, PLAYER_CLASSES)

    def test_class_starters_exist(self):
        for cls in PLAYER_CLASSES:
            self.assertIn(cls, CLASS_STARTERS)

    def test_spec_to_dict(self):
        spec = default_quick_start_spec()
        d = spec.to_dict()
        self.assertEqual(d["class"], "warrior")
        self.assertEqual(d["race"], "human")


class TestEngineUsesSpec(unittest.TestCase):
    def test_engine_accepts_spec(self):
        from engine.game_engine import GameEngine
        from ui.character_creator import CharacterSpec

        spec = CharacterSpec(
            name="Gandalf",
            race=CharacterRace.ELF,
            character_class=CharacterClass.WIZARD,
            stats={"strength": 8, "dexterity": 12, "constitution": 10,
                   "intelligence": 16, "wisdom": 14, "charisma": 12},
        )
        engine = GameEngine(
            llm_provider="heuristic",
            enable_npc_processes=False,
            player_spec=spec,
        )
        self.assertEqual(engine.player.name, "Gandalf")
        self.assertEqual(engine.player.character_class, CharacterClass.WIZARD)
        self.assertEqual(engine.player.race, CharacterRace.ELF)
        # Intelligence should be 16 + any race bonus already applied by creator,
        # but we passed final stats; should equal what we set.
        self.assertEqual(engine.player.intelligence, 16)
        try:
            engine.end_game()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
