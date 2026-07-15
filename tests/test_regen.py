"""P27.2 — passive wound recovery.

A wound knits slowly on its own when the hero is safe and provided for, so
chronic low HP isn't the default state — but never mid-fight, and never for a
dying, starving, parched, or badly infected body.
"""

import unittest

from engine.game_engine import GameEngine
from engine import regen
from world.monsters import build_monster


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        # clear any hostiles so the default state is SAFE
        for nid in list(self.engine.npc_manager.npcs):
            n = self.engine.npc_manager.npcs[nid]
            if getattr(n.character_class, "value", "") in regen._HOSTILE:
                self.engine.world.map.remove_character(n)
                self.engine.npc_manager.remove_npc(nid)
        # hurt but fed & watered
        self.p.metadata.update(hunger=10, thirst=10)
        self.p.metadata.pop("dying", None)
        self.p.metadata.pop("infection", None)
        self.p.hp = max(1, self.p.max_hp // 2)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestCanRegen(_Base):
    def test_a_safe_fed_wounded_hero_regens(self):
        self.assertTrue(regen.can_regen(self.engine))

    def test_full_hp_does_not_regen(self):
        self.p.hp = self.p.max_hp
        self.assertFalse(regen.can_regen(self.engine))

    def test_a_near_threat_stops_regen(self):
        foe = build_monster("goblin", (self.p.position[0] + 2,
                                       self.p.position[1]))
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.place_character(foe, *foe.position)
        self.assertFalse(regen.can_regen(self.engine))

    def test_starving_stops_regen(self):
        self.p.metadata["hunger"] = 95
        self.assertFalse(regen.can_regen(self.engine))

    def test_parched_stops_regen(self):
        self.p.metadata["thirst"] = 95
        self.assertFalse(regen.can_regen(self.engine))

    def test_dying_stops_regen(self):
        self.p.metadata["dying"] = 2
        self.assertFalse(regen.can_regen(self.engine))

    def test_bad_infection_stops_regen(self):
        self.p.metadata["infection"] = 80
        self.assertFalse(regen.can_regen(self.engine))


class TestTick(_Base):
    def test_heals_on_the_interval(self):
        self.engine.turn_counter = regen.REGEN_INTERVAL * 3   # a tick turn
        before = self.p.hp
        healed = regen.tick_hp_regen(self.engine)
        self.assertEqual(healed, 1)
        self.assertEqual(self.p.hp, before + 1)

    def test_no_heal_off_the_interval(self):
        self.engine.turn_counter = regen.REGEN_INTERVAL * 3 + 1
        before = self.p.hp
        self.assertEqual(regen.tick_hp_regen(self.engine), 0)
        self.assertEqual(self.p.hp, before)

    def test_never_overheals(self):
        self.p.hp = self.p.max_hp - 1
        self.engine.turn_counter = regen.REGEN_INTERVAL
        regen.tick_hp_regen(self.engine)
        self.assertEqual(self.p.hp, self.p.max_hp)
        # and no further gain past full
        self.engine.turn_counter = regen.REGEN_INTERVAL * 2
        self.assertEqual(regen.tick_hp_regen(self.engine), 0)

    def test_well_rested_regens_faster(self):
        from characters.status_effects import apply_effect
        base = regen.regen_interval(self.engine)
        apply_effect(self.p, "well_rested", duration=240)
        self.assertLess(regen.regen_interval(self.engine), base)


class TestIntegration(_Base):
    def test_hp_climbs_over_safe_travel(self):
        # walking safe ground for a while mends real HP (ends chronic low HP)
        self.p.hp = max(1, self.p.max_hp // 3)
        before = self.p.hp
        for _ in range(regen.REGEN_INTERVAL * 4):
            self.engine.advance_turn()
        self.assertGreater(self.p.hp, before)


if __name__ == "__main__":
    unittest.main()
