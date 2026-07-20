"""The undead (George): a rich roster with true undead traits — immune to
poison/plague/fear, weak to holy/radiant/fire (and a mace vs a skeleton),
and the cleric's Turn Undead that routs and destroys them."""

import unittest

from engine.game_engine import GameEngine
from engine import undead
from world.monsters import build_monster
from ui.character_creator import CharacterSpec
from characters.character_types import CharacterClass, CharacterRace


class TestTraits(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_roster_is_flagged_undead(self):
        for mid in ("zombie", "skeleton_warrior", "ghoul", "wight", "wraith",
                    "specter", "vampire", "mummy", "revenant", "death_knight",
                    "lich"):
            m = build_monster(mid, (1, 1))
            self.assertTrue(undead.is_undead(m), mid)

    def test_damage_types(self):
        sk = build_monster("skeleton_warrior", (1, 1))
        self.assertGreater(undead.damage_multiplier(sk, "holy"), 1.0)
        self.assertGreater(undead.damage_multiplier(sk, "bludgeon"), 1.0)
        self.assertEqual(undead.damage_multiplier(sk, "poison"), 0.0)
        self.assertLess(undead.damage_multiplier(sk, "pierce"), 1.0)
        self.assertGreaterEqual(
            undead.damage_multiplier(build_monster("mummy", (1, 1)), "fire"),
            2.0)
        self.assertGreater(
            undead.damage_multiplier(build_monster("vampire", (1, 1)),
                                     "silver"), 1.0)

    def test_living_is_unaffected(self):
        from world.wildlife import build_wildlife
        deer = build_wildlife("deer", (1, 1))
        self.assertFalse(undead.is_undead(deer))
        self.assertEqual(undead.damage_multiplier(deer, "holy"), 1.0)

    def test_undead_immune_to_poison_and_fear(self):
        from characters.status_effects import apply_effect, has_effect
        z = build_monster("zombie", (1, 1))
        apply_effect(z, "poisoned", 5)
        apply_effect(z, "frightened", 5, value=2)
        self.assertFalse(has_effect(z, "poisoned"))
        self.assertFalse(has_effect(z, "frightened"))

    def test_combat_holy_weapon_hits_undead_harder(self):
        from items.item_registry import create_item
        from characters import equipment as eqp
        p = self.engine.player
        sun = create_item("sunblade")            # a holy legendary blade
        if sun is None or (sun.damage_kind or "") != "holy":
            self.skipTest("no holy weapon")
        p.inventory.append(sun)
        eqp.equip(p, sun)
        from engine.combat_math import damage_type_modifier
        sk = build_monster("skeleton_warrior", (1, 1))
        boosted = damage_type_modifier(p, sk, 10)
        self.assertGreater(boosted, 10)


class TestTurnUndead(unittest.TestCase):
    def _engine(self, cls=CharacterClass.CLERIC):
        spec = CharacterSpec(name="Ser Light", race=CharacterRace.HUMAN,
                             character_class=cls,
                             stats={"strength": 12, "dexterity": 10,
                                    "constitution": 12, "intelligence": 10,
                                    "wisdom": 16, "charisma": 12})
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                       player_spec=spec)
        e.start_game()
        return e

    def test_cleric_turns_nearby_undead(self):
        e = self._engine()
        p = e.player
        p.level = 8
        px, py = p.position
        skels = []
        for i in range(3):
            s = build_monster("skeleton_warrior", (px + 1 + i, py))
            s.id = f"turn_skel_{i}"
            e.npc_manager.add_npc(s)
            skels.append(s)
        msg = undead.turn_undead(e, p)
        self.assertIn("dead", msg.lower())
        # some crumble, the rest rout
        routed_or_slain = sum(1 for s in skels
                              if not s.is_alive() or s.metadata.get("broken"))
        self.assertEqual(routed_or_slain, 3)
        e.end_game()

    def test_turn_undead_spell_casts(self):
        e = self._engine()
        p = e.player
        p.level = 8
        p.metadata["spells_known"] = ["turn_undead"]
        p.metadata["mana"] = 30
        z = build_monster("zombie", (p.position[0] + 1, p.position[1]))
        z.id = "turn_zombie"
        e.npc_manager.add_npc(z)
        msg = e.cast_spell("turn_undead")
        self.assertIn("holy", msg.lower())
        e.end_game()

    def test_non_holy_class_cannot_turn(self):
        e = self._engine(CharacterClass.WIZARD)
        self.assertFalse(undead.can_turn(e.player))
        e.end_game()


class TestNecromancy(unittest.TestCase):
    def _necro(self):
        spec = CharacterSpec(name="Mortis", race=CharacterRace.HUMAN,
                             character_class=CharacterClass.WIZARD,
                             stats={"strength": 10, "dexterity": 10,
                                    "constitution": 12, "intelligence": 16,
                                    "wisdom": 12, "charisma": 10})
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                       player_spec=spec)
        e.start_game()
        p = e.player
        p.level = 12
        p.metadata["spells_known"] = ["animate_dead", "command_undead"]
        p.metadata["mana"] = 60
        p.metadata["max_mana"] = 60
        return e, p

    def test_animate_dead_raises_a_minion(self):
        from engine import necromancy
        e, p = self._necro()
        self.assertTrue(necromancy.is_necromancer(p))
        n0 = len(necromancy.minions(e, p))
        msg = e.cast_spell("animate_dead")
        self.assertIn("raise", msg.lower())
        mins = necromancy.minions(e, p)
        self.assertEqual(len(mins), n0 + 1)
        self.assertTrue(undead.is_undead(mins[0]))
        self.assertIn(mins[0].id, e.companion_manager.party)
        e.end_game()

    def test_minion_cap(self):
        from engine import necromancy
        e, p = self._necro()
        cap = necromancy.minion_cap(p)
        for _ in range(cap + 3):
            necromancy.animate_dead(e, p)
        self.assertLessEqual(len(necromancy.minions(e, p)), cap)
        e.end_game()

    def test_lich_ascension_gated_and_works(self):
        from engine import necromancy
        e, p = self._necro()
        # a non-necromancer of low level cannot ascend
        p.level = 3
        self.assertIn("mighty", necromancy.lich_ascension(e, p).lower())
        p.level = 12
        msg = necromancy.lich_ascension(e, p)
        self.assertTrue(undead.is_undead(p))
        self.assertEqual(p.metadata.get("undead_type"), "lich")
        e.end_game()

    def test_phylactery_item_ascends(self):
        from items.item_registry import create_item
        e, p = self._necro()
        phyl = create_item("phylactery")
        self.assertIsNotNone(phyl)
        p.inventory.append(phyl)
        e.use_item("Soul Phylactery")
        self.assertTrue(undead.is_undead(p))
        e.end_game()

    def test_pallid_codex_makes_a_necromancer(self):
        from engine import necromancy
        from items.item_registry import create_item
        spec = CharacterSpec(name="Novice", race=CharacterRace.HUMAN,
                             character_class=CharacterClass.WIZARD,
                             stats={"strength": 10, "dexterity": 10,
                                    "constitution": 12, "intelligence": 16,
                                    "wisdom": 12, "charisma": 10})
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                       player_spec=spec)
        e.start_game()
        p = e.player
        self.assertFalse(necromancy.is_necromancer(p))
        tome = create_item("tome_necromancy")
        p.inventory.append(tome)
        e.use_item("The Pallid Codex")
        self.assertTrue(necromancy.is_necromancer(p))
        self.assertEqual(p.metadata.get("specialization"), "necromancer")
        e.end_game()

    def test_vampire_spread(self):
        from engine import necromancy
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        victim = build_monster("bandit", (5, 5))  # a living person
        victim.metadata["undead"] = False
        necromancy.become_undead(e, victim, "vampire_spawn", source="a bite")
        self.assertTrue(undead.is_undead(victim))
        self.assertEqual(victim.metadata.get("undead_type"), "vampire_spawn")
        e.end_game()


if __name__ == "__main__":
    unittest.main()
