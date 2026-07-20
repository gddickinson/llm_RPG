"""Richer skill roster: combat/magic/utility skills that feed real power
(weaponry/defense/marksmanship → combat, spellcraft → mana, medicine →
healing, thievery → locks), trained by doing."""

import unittest

from engine.game_engine import GameEngine
from engine import skill_combat as sc
from engine.skill_progression import (add_skill_xp, total_xp_for_level,
                                      get_skill_level, get_skill_xp,
                                      all_skill_ids)


class TestRoster(unittest.TestCase):
    def test_new_skills_registered(self):
        ids = all_skill_ids()
        for s in ("weaponry", "defense", "marksmanship", "spellcraft",
                  "medicine", "thievery"):
            self.assertIn(s, ids)

    def test_every_skill_has_a_pet(self):
        import json
        with open("data/pets.json", encoding="utf-8") as fh:
            pets = json.load(fh)
        for s in all_skill_ids():
            self.assertIn(s, pets, f"skill {s} needs a pet")


class TestEffects(unittest.TestCase):
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

    def _raise(self, skill, lvl):
        add_skill_xp(self.p, skill, total_xp_for_level(lvl))

    def test_combat_bonuses_scale(self):
        self.assertEqual(sc.weapon_damage_bonus(self.p), 0)
        self._raise("weaponry", 16)
        self.assertEqual(sc.weapon_damage_bonus(self.p), 16 // 8)
        self._raise("defense", 20)
        self.assertGreaterEqual(sc.armor_ac_bonus(self.p), 20 // 10)
        self._raise("marksmanship", 24)
        self.assertEqual(sc.ranged_damage_bonus(self.p), 24 // 8)

    def test_spellcraft_delta_safe_then_boosts_mana(self):
        from engine.spells import ensure_mana
        ensure_mana(self.p)
        base = self.p.metadata["max_mana"]
        ensure_mana(self.p)                       # no spellcraft → unchanged
        self.assertEqual(self.p.metadata["max_mana"], base)
        self._raise("spellcraft", 9)              # 9 // 3 = 3 mana
        ensure_mana(self.p)
        self.assertEqual(self.p.metadata["max_mana"], base + 3)

    def test_medicine_and_thievery_bonuses(self):
        self._raise("medicine", 20)
        self.assertEqual(sc.heal_bonus(self.p), 20 // 5)
        self._raise("thievery", 18)
        self.assertEqual(sc.lock_bonus(self.p), 18 // 6)


class TestUsePaths(unittest.TestCase):
    def setUp(self):
        from ui.character_creator import CharacterSpec
        from characters.character_types import CharacterClass, CharacterRace
        spec = CharacterSpec(name="Mage", race=CharacterRace.HUMAN,
                             character_class=CharacterClass.WIZARD,
                             stats={"strength": 10, "dexterity": 12,
                                    "constitution": 10, "intelligence": 16,
                                    "wisdom": 12, "charisma": 10})
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False, player_spec=spec)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_casting_trains_spellcraft(self):
        before = get_skill_xp(self.p, "spellcraft")
        self.p.metadata["mana"] = 100
        self.p.metadata["spells_known"] = ["heal"]
        try:
            self.engine.cast_spell("heal")
        except Exception:
            pass
        self.assertGreater(get_skill_xp(self.p, "spellcraft"), before)


if __name__ == "__main__":
    unittest.main()
