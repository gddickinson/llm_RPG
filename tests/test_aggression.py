"""P37.6b — hostile aggression: adjacent monsters press the attack every turn,
and a natural attack so a weaponless beast hits hard."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_aggro_"))

import random
import unittest

from world.monsters import build_monster


class TestNaturalDamage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_weaponless_monster_uses_its_natural_attack(self):
        cs = self.engine.combat_system
        wolf = build_monster("wolf", (0, 0))
        # the wolf carries no weapon, but its fangs (natural_damage) count
        self.assertEqual(wolf.metadata.get("natural_damage"), 4)
        self.assertEqual(cs._best_weapon_damage(wolf), 4)

    def test_tough_foes_hit_harder_than_weak_ones(self):
        cs = self.engine.combat_system
        troll = cs._best_weapon_damage(build_monster("wandering_troll", (0, 0)))
        goblin = cs._best_weapon_damage(build_monster("goblin", (0, 0)))
        self.assertGreater(troll, goblin)


class TestAggression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def _place(self, mid, dx, dy, mono_id="agg_test"):
        eng = self.engine
        px, py = eng.player.position
        m = build_monster(mid, (px + dx, py + dy))
        m.id = mono_id
        eng.npc_manager.add_npc(m)
        eng.world.map.place_character(m, px + dx, py + dy)
        return m

    def _clear(self, m):
        try:
            self.engine.world.map.remove_character(m)
        except Exception:
            pass
        self.engine.npc_manager.npcs.pop(m.id, None)

    def test_adjacent_hostile_bites_every_turn(self):
        eng = self.engine
        eng.player.hp = eng.player.max_hp = 60
        eng.combat_system.rng = random.Random(0)     # deterministic hits
        m = self._place("wolf", 1, 0)
        try:
            hp0 = eng.player.hp
            # press over several turns; a bite lands and drops the hero's HP
            for _ in range(8):
                eng.aggression.update()
            self.assertLess(eng.player.hp, hp0,
                            "an adjacent wolf should draw blood every turn")
        finally:
            self._clear(m)

    def test_indoors_player_is_not_bitten_by_overworld_hostile(self):
        # George 2026-07-15: an invisible Mire Stalker sitting at a low overworld
        # tile bit the hero in EVERY building until dead — a player in an
        # interior is a SEPARATE coordinate space and must be unreachable.
        eng = self.engine
        eng.player.hp = eng.player.max_hp = 60
        m = self._place("wolf", 1, 0)                # 'adjacent' in coord space
        saved = getattr(eng, "current_interior", None)
        eng.current_interior = object()             # the hero is indoors
        try:
            for _ in range(8):
                self.assertEqual(eng.aggression.update(), 0)
            self.assertEqual(eng.player.hp, 60, "no bite reaches an indoor hero")
        finally:
            eng.current_interior = saved
            self._clear(m)

    def test_non_adjacent_hostile_does_not_bite(self):
        eng = self.engine
        eng.player.hp = eng.player.max_hp = 60
        m = self._place("wolf", 3, 0)                # 3 tiles away
        try:
            pressed = eng.aggression.update()
            self.assertEqual(pressed, 0)
            self.assertEqual(eng.player.hp, 60)
        finally:
            self._clear(m)

    def test_bite_tags_the_turn_for_the_double_attack_guard(self):
        eng = self.engine
        eng.player.hp = eng.player.max_hp = 60
        m = self._place("goblin", 1, 0)
        try:
            eng.aggression.update()
            self.assertEqual(m.metadata.get("_aggro_turn"), eng.turn_counter)
        finally:
            self._clear(m)

    def test_party_member_is_never_attacked(self):
        eng = self.engine
        m = self._place("wolf", 1, 0)
        try:
            eng.companion_manager.party.append(m.id)
            pressed = eng.aggression.update()
            self.assertEqual(pressed, 0, "a party member is not a hostile")
        finally:
            if m.id in eng.companion_manager.party:
                eng.companion_manager.party.remove(m.id)
            self._clear(m)


if __name__ == "__main__":
    unittest.main()
