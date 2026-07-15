"""Tests for the random encounters system."""

import unittest
import random

from engine.game_engine import GameEngine


class TestEncounters(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        # Force RNG so spawns are deterministic when we want them
        self.engine.encounter_manager.rng = random.Random(1)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_no_spawn_in_village(self):
        # Player default position should be in/near village; even if
        # wilderness, force player into a building tile (no spawn)
        from world.world_map import TerrainType
        # Find a road or building tile
        for y in range(self.engine.world.map.height):
            for x in range(self.engine.world.map.width):
                if self.engine.world.map.terrain[y][x] == TerrainType.ROAD:
                    self.engine.player.position = (x, y)
                    break
            else:
                continue
            break
        # Force encounter chance high then attempt spawn
        from world import encounters
        original = encounters.ENCOUNTER_CHANCE
        encounters.ENCOUNTER_CHANCE = 1.0
        try:
            msg = self.engine.encounter_manager.maybe_spawn()
            # Road isn't FOREST/GRASS, so should return None
            self.assertIsNone(msg)
        finally:
            encounters.ENCOUNTER_CHANCE = original

    def _deep_wild_grass(self):
        """A GRASS tile well away from any settlement (P27.1: near-town is a
        safe zone, so 'wilderness' must mean the deep wild)."""
        from world.world_map import TerrainType
        from world import encounters
        em = self.engine.encounter_manager
        wmap = self.engine.world.map
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.terrain[y][x] != TerrainType.GRASS:
                    continue
                d = em._nearest_settlement_dist((x, y))
                if d is None or d > encounters.FRINGE_RADIUS + 2:
                    return (x, y)
        return None

    def test_spawn_in_wilderness(self):
        spot = self._deep_wild_grass()
        if spot is None:
            self.skipTest("no deep-wild grass tile in this world")
        self.engine.player.position = spot
        self.engine.world.map.place_character(self.engine.player, *spot)
        from world import encounters
        original = encounters.ENCOUNTER_CHANCE
        encounters.ENCOUNTER_CHANCE = 1.0
        try:
            msg = self.engine.encounter_manager.maybe_spawn()
            self.assertTrue(msg, "Expected a wilderness spawn")
            self.assertIn("appears", msg)
        finally:
            encounters.ENCOUNTER_CHANCE = original


class TestDangerTiers(unittest.TestCase):
    """P27.1 — near-town/road is safer, the deep wild is more dangerous."""

    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.em = self.engine.encounter_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _a_settlement(self):
        from world import encounters
        for loc in self.engine.world.locations:
            if any(k in loc.name.lower() for k in encounters._SETTLEMENT_KEYS):
                return loc
        return None

    def test_no_wandering_spawn_in_the_town_safe_zone(self):
        from world.world_map import TerrainType
        from world import encounters
        town = self._a_settlement()
        self.assertIsNotNone(town)
        cx, cy = town.center()
        # a GRASS tile right beside the town centre (inside the safe radius)
        spot = None
        for r in range(1, encounters.SAFE_RADIUS):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    x, y = cx + dx, cy + dy
                    wmap = self.engine.world.map
                    if 0 <= x < wmap.width and 0 <= y < wmap.height \
                            and wmap.terrain[y][x] == TerrainType.GRASS:
                        spot = (x, y)
                        break
                if spot:
                    break
            if spot:
                break
        if spot is None:
            self.skipTest("no grass tile inside the town safe zone")
        self.engine.player.position = spot
        original = encounters.ENCOUNTER_CHANCE
        encounters.ENCOUNTER_CHANCE = 1.0
        try:
            self.assertIsNone(self.em.maybe_spawn(),
                              "the guarded town must have no wild spawns")
        finally:
            encounters.ENCOUNTER_CHANCE = original

    def test_danger_rises_with_distance_from_town(self):
        town = self._a_settlement()
        cx, cy = town.center()
        from world import encounters
        # on the fringe vs far out (place the player, read the multiplier)
        self.engine.player.position = (cx + encounters.FRINGE_RADIUS, cy)
        fringe = self.em.danger_multiplier()
        self.engine.player.position = (cx + encounters.FRINGE_RADIUS
                                       + encounters.FAR_STEP * 2, cy)
        far = self.em.danger_multiplier()
        self.assertGreater(far, fringe)

    def test_danger_multiplier_is_always_positive(self):
        # even in the fringe (so the weather/omen RATIO tests keep working)
        town = self._a_settlement()
        cx, cy = town.center()
        self.engine.player.position = (cx + 10, cy)
        self.assertGreater(self.em.danger_multiplier(), 0)


if __name__ == "__main__":
    unittest.main()


class TestOffscreenSpawning(unittest.TestCase):
    """P34.23: monsters spawn OFFSCREEN (beyond sight) and roam in, or emerge
    from a cave — nothing pops into existence in front of the hero."""

    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.engine.encounter_manager.rng = random.Random(3)
        # a clear grassy spot away from the walls
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        self.engine.player.position = (wmap.width // 2, wmap.height // 2)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_spawns_beyond_the_hero_sight(self):
        em = self.engine.encounter_manager
        vis = self.engine.effective_visibility()
        px, py = self.engine.player.position
        got = 0
        for _ in range(20):
            pos, origin = em._find_spawn_position()
            if pos is None:
                continue
            got += 1
            d = ((pos[0] - px) ** 2 + (pos[1] - py) ** 2) ** 0.5
            self.assertGreater(d, vis)              # offscreen — past the fog
            self.assertIn(origin, ("wild", "cave"))
        self.assertGreater(got, 0)

    def test_emerges_from_a_nearby_cave(self):
        from world.world_map import TerrainType
        em = self.engine.encounter_manager
        wmap = self.engine.world.map
        px, py = self.engine.player.position
        wmap.terrain[py][px + 7] = TerrainType.CAVE   # a cave just out of sight
        pos, origin = em._find_spawn_position()
        self.assertEqual(origin, "cave")
        # spawned adjacent to the cave mouth, not on it
        self.assertLessEqual(abs(pos[0] - (px + 7)) + abs(pos[1] - py), 1)


if __name__ == "__main__":
    unittest.main()
