"""M4 — workers rebuild the town via Worldcraft.

Each night a settlement with a builder clears its scars (rubble/scorched → grass)
through the same worldcraft ruleset the player uses; the healed terrain persists
for free (the map snapshot).
"""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class TestConstruction(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.cs = self.engine.construction
        setts = self.cs._settlements()
        if not setts:
            self.skipTest("no settlement")
        self.s = setts[0]

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _scatter_scars(self, n=6):
        cx, cy = self.s.center()
        scars = []
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                x, y = cx + dx, cy + dy
                if (0 <= x < self.wmap.width and 0 <= y < self.wmap.height
                        and self.wmap.get_terrain_at(x, y) == TerrainType.GRASS
                        and (x, y) not in self.wmap.characters):
                    self.wmap.set_terrain(
                        x, y, TerrainType.RUBBLE if len(scars) % 2
                        else TerrainType.SCORCHED)
                    scars.append((x, y))
                    if len(scars) >= n:
                        return scars
        return scars

    def _scar_count(self, scars):
        return sum(1 for t in scars if self.wmap.get_terrain_at(*t)
                   in (TerrainType.RUBBLE, TerrainType.SCORCHED))

    def test_folk_clear_the_scars(self):
        scars = self._scatter_scars()
        if len(scars) < 2:
            self.skipTest("no room for scars")
        self.assertTrue(self.cs._has_builder(self.s))
        before = self._scar_count(scars)
        self.cs.run_day()
        after = self._scar_count(scars)
        self.assertLess(after, before, "workers restore some scarred ground")

    def test_capped_per_night(self):
        scars = self._scatter_scars(6)
        if len(scars) < 5:
            self.skipTest("no room")
        before = self._scar_count(scars)
        self.cs._repair_around(self.s)
        healed = before - self._scar_count(scars)
        from engine.construction import MAX_PER_NIGHT
        self.assertLessEqual(healed, MAX_PER_NIGHT, "gradual, not all at once")

    def test_no_builder_no_repair(self):
        # remove every NPC so no builder is near
        for nid in list(self.engine.npc_manager.npcs):
            self.engine.npc_manager.remove_npc(nid)
        self.assertFalse(self.cs._has_builder(self.s))
        scars = self._scatter_scars()
        if not scars:
            self.skipTest("no room")
        before = self._scar_count(scars)
        self.cs.run_day()
        self.assertEqual(self._scar_count(scars), before, "no one to rebuild")

    def test_beats_name_the_settlement(self):
        self._scatter_scars()
        beats = self.cs.run_day()
        if beats:
            self.assertTrue(any("clear the ruin" in b for b in beats))
            self.assertFalse(any("Stable" in b or "Waystone" in b
                                 for b in beats), "clean settlement names")


if __name__ == "__main__":
    unittest.main()
