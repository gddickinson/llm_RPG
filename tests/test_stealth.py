"""Stealth & sneak attacks (GAP.3). Everything is gated on the opt-in
CRAWL stance, so default play is untouched (verified) while a sneaking
rogue can creep up and strike an unaware foe for heavy bonus damage."""

import unittest

from engine.game_engine import GameEngine
from engine import stealth
from world.monsters import build_monster


class TestStealthPure(unittest.TestCase):
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

    def test_sneaking_flag_follows_crawl(self):
        self.p.metadata.pop("_move_mode", None)
        self.assertFalse(stealth.is_sneaking(self.p))
        self.p.metadata["_move_mode"] = "crawl"
        self.assertTrue(stealth.is_sneaking(self.p))

    def test_evades_false_when_not_sneaking(self):
        self.p.metadata.pop("_move_mode", None)
        w = build_monster("wolf", (self.p.position[0] + 1,
                                   self.p.position[1]))
        # not sneaking → never evades, so pursuit/aggression are unchanged
        self.assertFalse(stealth.evades(self.engine, w))

    def test_evades_when_sneaking_and_far_and_hidden(self):
        self.p.metadata["_move_mode"] = "crawl"
        px, py = self.p.position
        far = build_monster("wolf", (px + 6, py))     # beyond a novice radius?
        # a roguish, dextrous sneaker shrinks the radius hard
        from characters.character_types import CharacterClass
        self.p.character_class = CharacterClass.ROGUE
        self.p.dexterity = 16
        self.p.level = 5
        r = stealth.detection_radius(self.engine, far)
        self.assertLessEqual(r, 3)
        self.assertTrue(stealth.evades(self.engine, far))

    def test_noticed_foe_is_not_evaded(self):
        self.p.metadata["_move_mode"] = "crawl"
        px, py = self.p.position
        w = build_monster("wolf", (px + 6, py))
        stealth.note_engaged(w)
        self.assertFalse(stealth.evades(self.engine, w),
                         "a foe that already saw you is not evaded")

    def test_sneak_attack_only_on_unaware(self):
        w = build_monster("wolf", (self.p.position[0] + 1,
                                   self.p.position[1]))
        self.p.metadata["_move_mode"] = "crawl"             # must be sneaking
        dmg, hit = stealth.sneak_attack(self.engine, self.p, w, 10)
        self.assertTrue(hit)
        self.assertGreater(dmg, 10)
        # once aware, no bonus
        stealth.note_engaged(w)
        dmg2, hit2 = stealth.sneak_attack(self.engine, self.p, w, 10)
        self.assertFalse(hit2)
        self.assertEqual(dmg2, 10)

    def test_sneak_attack_never_for_npc_attacker(self):
        self.p.metadata["_move_mode"] = "crawl"
        w = build_monster("wolf", self.p.position)
        dmg, hit = stealth.sneak_attack(self.engine, w, self.p, 10)
        self.assertFalse(hit)

    def test_no_sneak_when_not_sneaking(self):
        # a normal walk-up strike on a fresh foe is NOT a sneak attack
        w = build_monster("wolf", (self.p.position[0] + 1,
                                   self.p.position[1]))
        self.p.metadata.pop("_move_mode", None)
        dmg, hit = stealth.sneak_attack(self.engine, self.p, w, 10)
        self.assertFalse(hit)
        self.assertEqual(dmg, 10)


class TestStealthInCombat(unittest.TestCase):
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

    def test_first_strike_from_stealth_marks_aware_and_announces(self):
        px, py = self.p.position
        w = build_monster("wolf", (px + 1, py))
        w.id = "sneak_target"
        w.hp = w.max_hp = 200                # survive the blow to inspect state
        self.engine.npc_manager.add_npc(w)
        self.assertTrue(stealth.is_unaware(w))
        self.p.metadata["_move_mode"] = "crawl"   # sneaking → sneak attack

        class _MaxRoll:                      # force a guaranteed hit
            def randint(self, a, b):
                return b
        self.engine.combat_system.rng = _MaxRoll()
        self.engine.combat_system._resolve(self.p, w, "attack")
        # the blow marks it aware, so a follow-up is no sneak attack
        self.assertFalse(stealth.is_unaware(w))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("SNEAK ATTACK", log)

    def test_npc_attacking_player_becomes_aware(self):
        px, py = self.p.position
        w = build_monster("wolf", (px + 1, py))
        w.id = "aggressor"
        self.engine.npc_manager.add_npc(w)
        self.assertTrue(stealth.is_unaware(w))
        self.engine.combat_system._resolve(w, self.p, "attack")
        self.assertFalse(stealth.is_unaware(w),
                         "a foe that attacks you clearly knows you're there")


if __name__ == "__main__":
    unittest.main()
