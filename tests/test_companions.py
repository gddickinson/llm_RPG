"""Tests for the companion / party system."""

import unittest

from engine.game_engine import GameEngine


class TestCompanions(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_cannot_recruit_unfriendly(self):
        # Pick the minstrel (bard) — recruitable class
        minstrel = self.engine.npc_manager.get_npc("minstrel_01")
        self.assertIsNotNone(minstrel)
        minstrel.relationships[self.engine.player.id] = 0
        msg = self.engine.recruit("minstrel_01")
        self.assertIn("trust", msg.lower())
        self.assertEqual(len(self.engine.party_members()), 0)

    def test_recruit_friendly(self):
        minstrel = self.engine.npc_manager.get_npc("minstrel_01")
        minstrel.relationships[self.engine.player.id] = 50
        msg = self.engine.recruit("minstrel_01")
        self.assertIn("joins", msg.lower())
        self.assertEqual(len(self.engine.party_members()), 1)

    def test_dismiss(self):
        minstrel = self.engine.npc_manager.get_npc("minstrel_01")
        minstrel.relationships[self.engine.player.id] = 50
        self.engine.recruit("minstrel_01")
        msg = self.engine.dismiss_companion("minstrel_01")
        self.assertIn("parts ways", msg.lower())
        self.assertEqual(len(self.engine.party_members()), 0)

    def test_companion_follows(self):
        minstrel = self.engine.npc_manager.get_npc("minstrel_01")
        minstrel.relationships[self.engine.player.id] = 50
        # Place minstrel far from player
        self.engine.world.map.remove_character(minstrel)
        minstrel.position = (0, 0)
        self.engine.world.map.place_character(minstrel, 0, 0)
        # Place player at known location
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (10, 10)
        self.engine.world.map.place_character(self.engine.player, 10, 10)
        self.engine.recruit("minstrel_01")
        # Enough follow ticks to cover worldgen detours (lakes, walls)
        for _ in range(40):
            self.engine.companion_manager.update()
        d = ((minstrel.position[0] - 10) ** 2 +
             (minstrel.position[1] - 10) ** 2) ** 0.5
        # Should be much closer than 14 (initial diagonal distance)
        self.assertLess(d, 8)

    def test_companion_trapped_on_building_emerges(self):
        # George: a companion recruited THROUGH A WINDOW starts on the guild
        # hall's BUILDING footprint (un-walkable) close to the leader — so it's
        # NOT "far", but it can't path out the door and was stuck inside
        # forever. update() should pull it onto a walkable tile by the leader.
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        minstrel = self.engine.npc_manager.get_npc("minstrel_01")
        minstrel.relationships[self.engine.player.id] = 50
        self.engine.recruit("minstrel_01")
        # a clear grassy patch for the leader to stand in / rejoin at
        for yy in range(8, 15):
            for xx in range(8, 15):
                wmap.terrain[yy][xx] = TerrainType.GRASS
        wmap.remove_character(self.engine.player)
        self.engine.player.position = (11, 11)
        wmap.place_character(self.engine.player, 11, 11)
        # trap the minstrel on a BUILDING tile a few tiles off (near, not far)
        wmap.terrain[10][10] = TerrainType.BUILDING
        wmap.remove_character(minstrel)
        minstrel.position = (10, 10)
        wmap.place_character(minstrel, 10, 10)
        self.assertEqual(minstrel.metadata.get("order", "follow"), "follow")
        # Isolate the roster to just the companion so no RNG-spawned bystander
        # or hostile gives it something to fight/heal — with nothing else to do
        # it must reach the FOLLOW branch and emerge from the building. (Without
        # this the test flakes when the seeded world drops a brigand next door.)
        saved = dict(self.engine.npc_manager.npcs)
        self.engine.npc_manager.npcs = {minstrel.id: minstrel}
        try:
            self.engine.companion_manager.update()
        finally:
            self.engine.npc_manager.npcs = saved
        tx, ty = minstrel.position
        self.assertNotEqual(
            wmap.terrain[ty][tx], TerrainType.BUILDING,
            "the trapped companion should emerge onto a walkable tile")
        d = abs(tx - 11) + abs(ty - 11)
        self.assertLessEqual(d, 6, "it should rejoin near the leader")


if __name__ == "__main__":
    unittest.main()
