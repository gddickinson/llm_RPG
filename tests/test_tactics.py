"""Tactical verbs: opportunity attacks, disengage, shove, aimed shot (P5.3)."""

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType


def _open_ground(engine, need=4):
    """A run of open grass tiles; returns the west end."""
    wmap = engine.world.map
    for y in range(2, wmap.height - 2):
        for x in range(2, wmap.width - 2 - need):
            if all(wmap.get_terrain_at(x + i, y) == TerrainType.GRASS
                   for i in range(need)):
                return (x, y)
    return None


class TestTactics(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        spot = _open_ground(self.engine)
        if spot is None:
            self.skipTest("no open ground")
        self.spot = spot
        self.engine.world.map.remove_character(self.player)
        self.player.position = spot
        self.engine.world.map.place_character(self.player, *spot)
        # A wolf adjacent to the east
        self.wolf = build_monster("wolf", (spot[0] + 1, spot[1]))
        self.engine.npc_manager.add_npc(self.wolf)
        self.engine.world.map.place_character(self.wolf,
                                              *self.wolf.position)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_retreat_provokes_opportunity_attack(self):
        hp = self.player.hp
        moved = self.engine.move_player(-1, 0)   # step away west
        self.assertTrue(moved)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("lashes out", log)

    def test_careful_disengage_avoids_the_strike(self):
        t0 = self.engine.world.time
        moved = self.engine.move_player(-1, 0, careful=True)
        self.assertTrue(moved)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertNotIn("lashes out", log)
        self.assertGreaterEqual(self.engine.world.time - t0, 2,
                                "care costs extra time")

    def test_moving_within_melee_does_not_provoke(self):
        # Step north: wolf is still within 1 (diagonal) — no strike
        self.engine.move_player(0, -1)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertNotIn("lashes out", log)

    def test_shove_pushes_enemy_back(self):
        from engine.tactics import shove
        import random
        rig = random.Random()
        rolls = iter([15, 8])   # player wins by 7 — a plain success
        rig.randint = lambda a, b: next(rolls)
        before = self.wolf.position
        msg = shove(self.engine, rng=rig)
        self.assertIn("staggering", msg)
        self.assertEqual(self.wolf.position,
                         (before[0] + 1, before[1]))

    def test_failed_shove_holds_ground(self):
        from engine.tactics import shove
        import random
        rig = random.Random()
        rolls = iter([8, 15])   # player loses by 7 — no counter-crit
        rig.randint = lambda a, b: next(rolls)
        before = self.wolf.position
        msg = shove(self.engine, rng=rig)
        self.assertIn("hold", msg)
        self.assertEqual(self.wolf.position, before)

    def test_shove_without_adjacent_enemy(self):
        from engine.tactics import shove
        self.wolf.position = (self.spot[0] + 20, self.spot[1])
        msg = shove(self.engine)
        self.assertIn("No enemy", msg)

    def test_aimed_shot_bonus_damage_and_time(self):
        from items.item_registry import create_item
        from characters import equipment as eq
        bow = create_item("bow")
        arrows = create_item("arrow", quantity=5)
        self.player.inventory += [bow, arrows]
        eq.equip(self.player, bow)
        t0 = self.engine.world.time
        msg = self.engine.shoot_ranged(aimed=True)
        self.assertIn("loose", msg)
        self.assertGreaterEqual(self.engine.world.time - t0, 2)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-5:])
        self.assertIn("careful aim", log)


if __name__ == "__main__":
    unittest.main()
