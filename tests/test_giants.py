"""Giants + nightly labor tests (P10.5)."""

import unittest

from engine.game_engine import GameEngine
from engine.giants import (GIANT_COOLDOWN, giant_tick, is_giant,
                           run_night_labor)
from world.monsters import build_monster
from world.world_map import TerrainType


class _AlwaysRng:
    """Deterministic rng stub: every chance roll succeeds."""

    def random(self):
        return 0.0


class TestGiants(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.player = self.engine.player
        # a quiet corner of grass to stage scenes on
        self.ox, self.oy = self.wmap.width - 12, self.wmap.height - 10
        for y in range(self.oy - 4, self.oy + 6):
            for x in range(self.ox - 4, self.ox + 8):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put_player(self, x, y):
        self.wmap.remove_character(self.player)
        self.player.position = (x, y)
        self.wmap.place_character(self.player, x, y)

    def _spawn_giant(self, x, y):
        g = build_monster("hill_giant", (x, y))
        self.engine.npc_manager.add_npc(g)
        self.wmap.place_character(g, x, y)
        return g

    def test_hill_giant_template_is_a_giant(self):
        g = self._spawn_giant(self.ox, self.oy)
        self.assertTrue(is_giant(g))
        wolf = build_monster("wolf", (self.ox + 3, self.oy + 3))
        self.assertFalse(is_giant(wolf))

    def test_giant_smashes_walls_into_deep_rubble(self):
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.BUILDING
        g = self._spawn_giant(self.ox, self.oy)
        self._put_player(self.ox - 4, self.oy - 4)
        for _ in range(30):
            giant_tick(self.engine, g)
            g.metadata["giant_cd"] = 0
            if self.wmap.terrain[self.oy][self.ox + 1] == \
                    TerrainType.RUBBLE:
                break
        self.assertEqual(self.wmap.terrain[self.oy][self.ox + 1],
                         TerrainType.RUBBLE,
                         "a giant must bring the wall down")
        self.assertGreaterEqual(
            self.engine.tile_damage.depth_at(self.ox + 1, self.oy), 2,
            "giants leave DEEP rubble — blocked until cleared")

    def test_boulder_maims_the_player_never_kills(self):
        g = self._spawn_giant(self.ox, self.oy)
        self._put_player(self.ox + 5, self.oy)
        self.player.hp = 4          # one boulder would be lethal
        acted = giant_tick(self.engine, g)
        self.assertTrue(acted, "a giant in range must hurl")
        self.assertEqual(self.player.hp, 1,
                         "boulders maim; the story kills")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("boulder", log.lower())

    def test_boulder_splash_crushes_bystanders(self):
        g = self._spawn_giant(self.ox, self.oy)
        self._put_player(self.ox + 5, self.oy)
        self.player.hp = self.player.max_hp
        bystander = build_monster("wolf", (self.ox + 6, self.oy))
        bystander.hp = bystander.max_hp = 2
        self.engine.npc_manager.add_npc(bystander)
        self.wmap.place_character(bystander, *bystander.position)
        self.assertTrue(giant_tick(self.engine, g))
        self.assertFalse(bystander.is_alive(),
                         "splash beside the impact is real")

    def test_giant_acts_on_a_cooldown(self):
        g = self._spawn_giant(self.ox, self.oy)
        self._put_player(self.ox + 5, self.oy)
        self.assertTrue(giant_tick(self.engine, g))
        self.assertEqual(g.metadata["giant_cd"], GIANT_COOLDOWN)
        self.assertFalse(giant_tick(self.engine, g),
                         "spent giants rest between acts")

    def test_night_labor_clears_rubble_by_buildings(self):
        loc = next(l for l in self.engine.world.locations
                   if l.name in self.engine.interiors)
        ex, ey = loc.x - 1, loc.y
        self.engine.tile_damage.add_rubble(ex, ey, depth=1)
        total_before = sum(
            self.engine.tile_damage.rubble_depth.values())
        acts = run_night_labor(self.engine, _AlwaysRng())
        self.assertGreater(acts, 0)
        self.assertEqual(
            sum(self.engine.tile_damage.rubble_depth.values()),
            total_before,
            "work crews MOVE debris, never delete it")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("[Realm]", log)

    def test_forest_regrows_beside_living_woods(self):
        x, y = self.ox, self.oy
        self.wmap.terrain[y][x] = TerrainType.SCORCHED
        self.wmap.terrain[y][x + 1] = TerrainType.FOREST
        self.wmap.terrain[y][x - 1] = TerrainType.FOREST
        run_night_labor(self.engine, _AlwaysRng())
        self.assertEqual(self.wmap.terrain[y][x], TerrainType.FOREST,
                         "scorched ground beside woods regrows")


if __name__ == "__main__":
    unittest.main()
