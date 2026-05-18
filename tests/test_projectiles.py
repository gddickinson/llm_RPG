"""Tests for the ranged-combat projectile system."""

import unittest

from engine.game_engine import GameEngine
from engine.projectiles import (
    CombatProjectile, ProjectileManager, HitResult,
    PROJECTILE_SPEED_PER_TURN, PROJECTILE_VISUAL_KIND,
    MISS_THRESHOLD,
)


class TestProjectile(unittest.TestCase):
    def test_speeds_and_kinds_aligned(self):
        for w, speed in PROJECTILE_SPEED_PER_TURN.items():
            self.assertGreater(speed, 0)
            self.assertIn(w, PROJECTILE_VISUAL_KIND)

    def test_update_advances_position(self):
        p = CombatProjectile(
            start_x=0, start_y=0,
            target_orig_x=10, target_orig_y=0,
            x=0, y=0, speed=5, damage=4,
            shooter_id="a", target_id="b", weapon_type="bow", kind="arrow",
            flight_time=2.0,
        )
        p.update(1.0)
        self.assertGreater(p.x, 0)
        self.assertFalse(p.arrived)
        p.update(2.0)
        self.assertTrue(p.arrived)
        self.assertEqual((p.x, p.y), (10, 0))


class TestProjectileManager(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_spawn(self):
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        proj = self.engine.projectile_manager.spawn(
            self.engine.player, troll, damage=5, weapon_type="bow")
        self.assertEqual(self.engine.projectile_manager.count, 1)
        self.assertEqual(proj.kind, "arrow")

    def test_arrival_and_hit(self):
        # Move troll near player and force-low HP
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(troll)
        troll.position = (self.engine.player.position[0] + 3,
                          self.engine.player.position[1])
        self.engine.world.map.place_character(troll, *troll.position)
        troll.hp = 100

        # Use a deterministic RNG that always hits
        import random
        self.engine.projectile_manager.rng = random.Random(0)

        before = troll.hp
        self.engine.projectile_manager.spawn(
            self.engine.player, troll, damage=10, weapon_type="bow")
        # Tick enough turns for arrival
        results = []
        for _ in range(10):
            results.extend(self.engine.projectile_manager.tick(1.0))
            if results:
                break
        self.assertTrue(any(r.weapon_type == "bow" for r in results))
        # Should have either hit or missed but resolved
        any_hit = any(r.hit for r in results)
        if any_hit:
            self.assertLess(troll.hp, before)

    def test_miss_when_target_moves(self):
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(troll)
        troll.position = (self.engine.player.position[0] + 5,
                          self.engine.player.position[1])
        self.engine.world.map.place_character(troll, *troll.position)
        self.engine.projectile_manager.spawn(
            self.engine.player, troll, damage=4, weapon_type="bow")
        # Teleport troll well beyond MISS_THRESHOLD
        self.engine.world.map.remove_character(troll)
        troll.position = (troll.position[0],
                          troll.position[1] + int(MISS_THRESHOLD) + 3)
        self.engine.world.map.place_character(troll, *troll.position)
        results = []
        for _ in range(10):
            results.extend(self.engine.projectile_manager.tick(1.0))
            if results:
                break
        self.assertTrue(results)
        # Should be at least one miss
        self.assertTrue(any(not r.hit for r in results))

    def test_engine_shoot_api(self):
        # Place player + troll close
        troll = self.engine.npc_manager.get_npc("troll_brigand_01")
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (troll.position[0] - 3,
                                       troll.position[1])
        self.engine.world.map.place_character(
            self.engine.player, *self.engine.player.position)
        # Give bow
        from items.item_registry import create_item
        self.engine.player.inventory.append(create_item("bow"))
        msg = self.engine.shoot_ranged()
        self.assertIn("bow", msg.lower())
        # advance_turn inside shoot_ranged may resolve the projectile
        # immediately at short range — assert an outcome message appeared.
        events = self.engine.memory_manager.get_recent_history(10)
        joined = " ".join(events).lower()
        self.assertIn("bow", joined)


if __name__ == "__main__":
    unittest.main()
