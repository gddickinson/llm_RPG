"""T4.4 — skills feed combat power.

A few skills sharpen you in a fight: smithing hones gear (+weapon damage, +AC),
agility makes you harder to hit (+AC), hunting fells beasts harder (+damage vs
monster/animal). Data-driven from each skill's `combat` block; wired into
`effects` (AC + weapon damage) and `combat_system` (the beast bonus).
"""

import unittest

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from engine import effects, skill_combat
from engine.skill_progression import add_skill_xp, get_skill_level, \
    total_xp_for_level


def _hero(cls=CharacterClass.WARRIOR):
    return Character(id="h", name="Hero", character_class=cls,
                     race=CharacterRace.HUMAN, level=1, strength=12,
                     dexterity=12, constitution=12, intelligence=10,
                     wisdom=10, charisma=10, hp=20, max_hp=20, position=(0, 0),
                     metadata={})


def _train(char, skill, level):
    add_skill_xp(char, skill, total_xp_for_level(level))
    assert get_skill_level(char, skill) >= level - 1


class TestScaling(unittest.TestCase):
    def test_no_skill_no_bonus(self):
        h = _hero()
        self.assertEqual(skill_combat.weapon_damage_bonus(h), 0)
        self.assertEqual(skill_combat.armor_ac_bonus(h), 0)
        self.assertEqual(skill_combat.combat_summary(h), [])

    def test_smithing_hones_gear(self):
        h = _hero()
        _train(h, "smithing", 48)          # 48//12 dmg, 48//16 ac
        self.assertEqual(skill_combat.weapon_damage_bonus(h), 4)
        self.assertGreaterEqual(skill_combat.armor_ac_bonus(h), 3)

    def test_agility_adds_dodge_ac(self):
        h = _hero()
        _train(h, "agility", 36)           # 36//12 = 3
        self.assertEqual(skill_combat.armor_ac_bonus(h), 3)

    def test_bonus_grows_with_level(self):
        low, high = _hero(), _hero()
        _train(low, "smithing", 12)
        _train(high, "smithing", 48)
        self.assertGreater(skill_combat.weapon_damage_bonus(high),
                           skill_combat.weapon_damage_bonus(low))


class TestBeastBonus(unittest.TestCase):
    def test_hunting_hits_beasts_not_people(self):
        h = _hero()
        _train(h, "hunting", 30)           # 30//10 = 3
        beast = _hero(CharacterClass.MONSTER)
        person = _hero(CharacterClass.WARRIOR)
        self.assertEqual(skill_combat.beast_damage_bonus(h, beast), 3)
        self.assertEqual(skill_combat.beast_damage_bonus(h, person), 0)

    def test_animals_count_as_beasts(self):
        h = _hero()
        _train(h, "hunting", 20)
        animal = _hero(CharacterClass.ANIMAL)
        self.assertEqual(skill_combat.beast_damage_bonus(h, animal), 2)


class TestEffectsIntegration(unittest.TestCase):
    def test_effective_ac_includes_skill(self):
        h = _hero()
        base = effects.effective_ac(h)
        _train(h, "agility", 24)           # +2 AC
        _train(h, "smithing", 32)          # +2 AC
        self.assertEqual(effects.effective_ac(h), base + 4)

    def test_effective_weapon_damage_includes_smithing(self):
        h = _hero()
        base = effects.effective_weapon_damage_bonus(h)
        _train(h, "smithing", 24)          # 24//12 = 2
        self.assertEqual(effects.effective_weapon_damage_bonus(h), base + 2)


class TestCombatIntegration(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_hunter_deals_more_to_a_beast(self):
        """The same seeded strike lands more on a beast than on a person — the
        hunting bonus is the only difference in the two identical resolves."""
        import random
        hunter = self.engine.player
        _train(hunter, "hunting", 50)              # +5 vs beasts
        cs = self.engine.combat_system
        results = {}
        for cls, key in ((CharacterClass.MONSTER, "beast"),
                         (CharacterClass.WARRIOR, "person")):
            target = _hero(cls)
            target.id = f"foe_{key}"
            target.hp = target.max_hp = 500        # never dies mid-test
            target.dexterity = 1                   # low AC → the hit lands
            cs.rng = random.Random(7)              # identical roll both times
            cs._resolve(hunter, target, "attack")
            results[key] = 500 - target.hp
        self.assertGreater(results["beast"], 0, f"the strike must land: {results}")
        self.assertEqual(results["beast"] - results["person"], 5,
                         f"hunting bonus must be exactly +5: {results}")


if __name__ == "__main__":
    unittest.main()
