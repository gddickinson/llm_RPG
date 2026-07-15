"""Body-part wound tests (P15.9)."""

import unittest

from engine.game_engine import GameEngine
from engine.skills import Skill, roll_check
from engine.wounds import (SEVERITY_MAX, WOUND_THRESHOLD,
                           attack_penalty, check_penalty, heal_wounds,
                           hp_ceiling, severity, status_line, total,
                           wound_part)
from items.item_registry import create_item


class _R:
    def __init__(self, roll=10, rand=0.5):
        self.roll = roll
        self.rand = rand

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def random(self):
        return self.rand


class TestWounds(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.player.metadata["wounds"] = {}

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_a_wound_climbs_severity_and_stops_at_max(self):
        for _ in range(5):
            wound_part(self.engine, "legs")
        self.assertEqual(severity(self.player, "legs"), SEVERITY_MAX,
                         "crippled is the floor of the bone")

    def test_head_wounds_bite_every_check(self):
        base = roll_check(self.player, Skill.PERCEPTION, dc=10,
                          rng=_R(10))[1]
        wound_part(self.engine, "head")
        wound_part(self.engine, "head")
        worn = roll_check(self.player, Skill.PERCEPTION, dc=10,
                          rng=_R(10))[1]
        self.assertEqual(base - worn, 2, "head 2 = -2 to the roll")
        self.assertEqual(check_penalty(self.player), -2)

    def test_arm_wounds_dock_the_swing_worse_arm_ignored(self):
        wound_part(self.engine, "right_arm")
        wound_part(self.engine, "right_arm")
        self.assertEqual(attack_penalty(self.player), 0,
                         "the good left arm still swings clean")
        wound_part(self.engine, "left_arm")
        self.assertEqual(attack_penalty(self.player), -1,
                         "both arms hurt: the better one is -1")

    def test_torso_wounds_cap_effective_hp(self):
        self.player.max_hp = 40
        self.assertEqual(hp_ceiling(self.player), 40)
        wound_part(self.engine, "torso")
        wound_part(self.engine, "torso")
        self.assertEqual(hp_ceiling(self.player), 28,
                         "two torso wounds = 70% ceiling")
        from engine.wounds import apply_hp_ceiling
        self.player.hp = 40
        apply_hp_ceiling(self.player)
        self.assertEqual(self.player.hp, 28)

    def test_leg_wounds_slow_the_step(self):
        from engine.wounds import step_minutes
        wound_part(self.engine, "legs")
        self.assertEqual(step_minutes(self.player), 1)

    def test_a_serious_hit_can_break_a_bone(self):
        from engine.wounds import maybe_wound
        # damage under the threshold: never wounds
        self.engine.combat_system.rng = _R(rand=0.0)
        maybe_wound(self.engine, WOUND_THRESHOLD - 1, self.player)
        self.assertEqual(total(self.player), 0)
        # a heavy blow with a doomed roll: wounds
        maybe_wound(self.engine, WOUND_THRESHOLD + 6, self.player)
        self.assertEqual(total(self.player), 1)

    def test_only_the_player_breaks(self):
        from engine.wounds import maybe_wound
        from world.monsters import build_monster
        wolf = build_monster("wolf", self.player.position)
        self.engine.combat_system.rng = _R(rand=0.0)
        maybe_wound(self.engine, 20, wolf)
        self.assertEqual(wolf.metadata.get("wounds", {}), {})

    def test_a_crippled_limb_festers(self):
        from engine.infection import infected
        self.engine.combat_system.rng = _R(rand=0.0)  # infect roll hits
        for _ in range(3):
            wound_part(self.engine, "legs", rng=_R(10))
        self.assertTrue(infected(self.player),
                        "a shattered leg turns septic")

    def test_wounds_knit_worst_first(self):
        wound_part(self.engine, "head")
        wound_part(self.engine, "head")   # head 2
        wound_part(self.engine, "legs")   # legs 1
        heal_wounds(self.player, 1)
        self.assertEqual(severity(self.player, "head"), 1,
                         "the deepest wound mends first")
        self.assertEqual(severity(self.player, "legs"), 1)

    def test_an_inn_night_knits_two(self):
        from engine import rest
        wound_part(self.engine, "head")
        wound_part(self.engine, "legs")
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      or "inn" in l.name.lower())
        wmap = self.engine.world.map
        wmap.remove_character(self.player)
        self.player.position = (tavern.x + tavern.width // 2,
                                tavern.y + tavern.height // 2)
        wmap.place_character(self.player, *self.player.position)
        self.player.gold = 100
        rest.sleep(self.engine)
        self.assertEqual(total(self.player), 0, "a real night mends")

    def test_battle_medicine_sets_a_limb(self):
        from engine.skill_actions import battle_medicine
        wound_part(self.engine, "right_arm")
        self.player.inventory = [create_item("bandage")]
        self.player.hp = 5
        self.engine.combat_system.rng = _R(roll=15)
        msg = battle_medicine(self.engine)
        self.assertIn("set the right arm", msg)
        self.assertEqual(total(self.player), 0)

    def test_the_status_line_reads_what_is_broken(self):
        self.assertEqual(status_line(self.player), "")
        wound_part(self.engine, "legs")
        line = status_line(self.player)
        self.assertIn("legs", line)
        self.assertIn("bruised", line)


if __name__ == "__main__":
    unittest.main()
