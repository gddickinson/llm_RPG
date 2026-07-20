"""NPCs seeded with calling-appropriate skills (a guard gets Weaponry, a
cleric Medicine, a blacksmith Smithing) — feeding the skill_combat power."""

import unittest

from engine import npc_skills
from engine.skill_progression import get_skill_level
from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace


def _npc(aid, cls, level=8, name=None):
    return Character(id=aid, name=name or aid,
                     character_class=cls, race=CharacterRace.HUMAN,
                     level=level, strength=12, dexterity=12,
                     constitution=12, intelligence=12, wisdom=12,
                     charisma=12, hp=30, max_hp=30)


class TestSeed(unittest.TestCase):
    def test_guard_gets_martial_skills(self):
        g = _npc("guard_01", CharacterClass.GUARD, level=8)
        npc_skills.seed(g)
        self.assertGreaterEqual(get_skill_level(g, "weaponry"), 8)
        self.assertGreaterEqual(get_skill_level(g, "defense"), 1)

    def test_cleric_gets_faith_skills(self):
        c = _npc("priest_x", CharacterClass.CLERIC, level=10)
        npc_skills.seed(c)
        self.assertGreater(get_skill_level(c, "spellcraft"), 0)
        # 'priest' role also grants medicine
        self.assertGreater(get_skill_level(c, "medicine"), 0)

    def test_role_from_id_grants_craft(self):
        # a blacksmith NPC is class MERCHANT — the craft is only in the name
        b = _npc("blacksmith_01", CharacterClass.MERCHANT, level=9)
        npc_skills.seed(b)
        self.assertGreater(get_skill_level(b, "smithing"), 0)   # role
        self.assertGreater(get_skill_level(b, "bartering"), 0)  # class

    def test_monsters_are_not_seeded(self):
        m = _npc("enc_wolf", CharacterClass.MONSTER, level=6)
        seeded = npc_skills.seed(m)
        self.assertFalse(seeded)
        self.assertEqual(get_skill_level(m, "weaponry"), 1)

    def test_player_char_is_left_alone(self):
        p = _npc("hero2", CharacterClass.WARRIOR, level=8)
        p.metadata["player_char"] = True
        self.assertFalse(npc_skills.seed(p))

    def test_idempotent(self):
        g = _npc("guard_02", CharacterClass.GUARD, level=8)
        self.assertTrue(npc_skills.seed(g))
        lvl = get_skill_level(g, "weaponry")
        self.assertFalse(npc_skills.seed(g))               # no re-seed
        self.assertEqual(get_skill_level(g, "weaponry"), lvl)

    def test_low_level_npc_has_no_combat_bonus(self):
        # conservative seeding: a weak NPC's skill is below the +1 threshold,
        # so its combat maths is unchanged (no balance disruption)
        from engine import skill_combat as sc
        g = _npc("guard_lo", CharacterClass.GUARD, level=2)
        npc_skills.seed(g)
        self.assertEqual(sc.weapon_damage_bonus(g), 0)

    def test_seasoned_npc_gains_real_power(self):
        from engine import skill_combat as sc
        g = _npc("guard_hi", CharacterClass.GUARD, level=16)
        npc_skills.seed(g)
        self.assertGreater(sc.weapon_damage_bonus(g), 0)


class TestViaAddNpc(unittest.TestCase):
    def test_add_npc_auto_seeds(self):
        from engine.game_engine import GameEngine
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        g = _npc("guard_added", CharacterClass.GUARD, level=12)
        engine.npc_manager.add_npc(g)
        self.assertTrue(g.metadata.get("skills_seeded"))
        self.assertGreater(get_skill_level(g, "weaponry"), 0)
        # the world's own NPCs got seeded too
        seeded = [n for n in engine.npc_manager.npcs.values()
                  if (n.metadata or {}).get("skills_seeded")]
        self.assertTrue(seeded)
        try:
            engine.end_game()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
