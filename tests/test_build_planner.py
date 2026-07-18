"""M5 — the player build/terraform planner.

A cursor near the hero paints tiles into a PLAN, then COMMITS the whole plan
through the M0 worldcraft ruleset (so placements obey the same skill/resource/
protected-ground rules); committed terrain persists for free.
"""

import unittest

try:
    import pygame
    _OK = True
except Exception:
    _OK = False

from engine.game_engine import GameEngine
from engine import worldcraft as wc
from world.world_map import TerrainType
from items.item_registry import create_item
from engine.skill_progression import add_skill_xp, total_xp_for_level


@unittest.skipUnless(_OK, "pygame not available")
class TestBuildPlanner(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.wmap = self.engine.world.map
        spot = self._open_spot()
        if spot is None:
            self.skipTest("no open ground")
        self.wmap.remove_character(self.p)
        self.p.position = spot
        self.wmap.place_character(self.p, *spot)
        add_skill_xp(self.p, "carpentry", total_xp_for_level(5))
        add_skill_xp(self.p, "foraging", total_xp_for_level(5))
        from ui.build_planner import BuildPlanner
        self.bp = BuildPlanner(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _open_spot(self):
        for y in range(2, self.wmap.height - 2):
            for x in range(2, self.wmap.width - 2):
                n = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                if all(self.wmap.get_terrain_at(*t) == TerrainType.GRASS
                       and not wc.protected(self.engine, *t)
                       for t in n) and (x, y) not in self.wmap.characters:
                    return (x, y)
        return None

    def _key(self, k):
        self.bp.handle_key(pygame.event.Event(pygame.KEYDOWN, key=k))

    def test_plan_and_commit(self):
        # till farmland — a labour brush (foraging skill, granted in setUp; a
        # forest is instant CREATION and takes a spell, not the build tool)
        from ui.build_planner import BRUSHES
        self.bp.brush = [b[0] for b in BRUSHES].index("farmland")
        self._key(pygame.K_RETURN)                     # plan till here
        self.assertEqual(len(self.bp.plan), 1)
        self._key(pygame.K_c)                          # commit
        self.assertEqual(self.bp.plan, {})
        self.assertEqual(self.wmap.get_terrain_at(*self.p.position),
                         TerrainType.FARMLAND)

    def test_cursor_bounded_by_reach(self):
        from ui.build_planner import REACH
        for _ in range(REACH + 5):
            self._key(pygame.K_RIGHT)
        px = self.p.position[0]
        self.assertLessEqual(self.bp.cx - px, REACH)

    def test_erase(self):
        self._key(pygame.K_RETURN)
        self.assertEqual(len(self.bp.plan), 1)
        self._key(pygame.K_x)
        self.assertEqual(len(self.bp.plan), 0)

    def test_wall_needs_stone(self):
        from ui.build_planner import BRUSHES
        self._key(pygame.K_RIGHT)      # a wall can't go on the hero's own tile
        target = (self.bp.cx, self.bp.cy)
        self.assertEqual(self.wmap.get_terrain_at(*target), TerrainType.GRASS)
        self.bp.brush = [b[0] for b in BRUSHES].index("building")
        self._key(pygame.K_RETURN)
        self._key(pygame.K_c)          # no stone → refused
        self.assertNotEqual(self.wmap.get_terrain_at(*target),
                            TerrainType.BUILDING)
        # now with stone
        self.p.add_item(create_item("stone", quantity=3))
        self._key(pygame.K_RETURN)
        self._key(pygame.K_c)
        self.assertEqual(self.wmap.get_terrain_at(*target),
                         TerrainType.BUILDING)

    def test_draw_runs(self):
        self._key(pygame.K_RETURN)
        surf = pygame.Surface((640, 480))
        self.bp.draw(surf, pygame.Rect(0, 0, 640, 480), 48)


if __name__ == "__main__":
    unittest.main()
