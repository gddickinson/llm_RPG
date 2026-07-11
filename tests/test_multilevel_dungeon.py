"""Multi-level dungeon tests (P9.5)."""

import unittest

from engine.game_engine import GameEngine
from world.dungeon import generate_multilevel
from world.world_map import TerrainType


class TestMultiLevelDungeon(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _enter(self):
        wmap = self.engine.world.map
        cave = next((x, y) for y in range(wmap.height)
                    for x in range(wmap.width)
                    if wmap.get_terrain_at(x, y) == TerrainType.CAVE)
        wmap.remove_character(self.player)
        self.player.position = cave
        wmap.place_character(self.player, *cave)
        self.engine.enter_dungeon()
        return self.engine.current_dungeon

    def test_dungeons_have_depth(self):
        top = self._enter()
        self.assertIsNotNone(top.level_below,
                             "dungeons must go deeper")
        depth = 1
        lv = top
        while lv.level_below is not None:
            lv = lv.level_below
            depth += 1
        self.assertIn(depth, (2, 3))
        self.assertIsNotNone(top.stairs_down)
        self.assertIsNotNone(top.level_below.stairs_up)

    def test_deeper_monsters_are_stronger(self):
        top = self._enter()
        deep = top.level_below
        top_monsters = [n for n in
                        self.engine.npc_manager.npcs.values()
                        if n.metadata.get("zone") == top.name]
        deep_monsters = [n for n in
                         self.engine.npc_manager.npcs.values()
                         if n.metadata.get("zone") == deep.name]
        self.assertTrue(top_monsters and deep_monsters)
        self.assertGreater(
            max(n.level for n in deep_monsters),
            min(n.level for n in top_monsters),
            "depth must scale danger")

    def test_the_deepest_floor_has_a_tyrant(self):
        top = self._enter()
        lv = top
        while lv.level_below is not None:
            lv = lv.level_below
        boss = [n for n in self.engine.npc_manager.npcs.values()
                if n.metadata.get("zone") == lv.name
                and "Tyrant" in n.name]
        self.assertEqual(len(boss), 1, "the den-lord must be home")
        self.assertGreater(boss[0].max_hp, 30)

    def test_stairs_descend_and_track_depth(self):
        top = self._enter()
        sx, sy = top.stairs_down
        self.player.position = (sx - 1, sy)
        # clear any monster on the stair
        for n in self.engine.npc_manager.npcs.values():
            if n.is_active() and tuple(n.position) == (sx, sy) and \
                    n.metadata.get("zone") == top.name:
                n.defeat()
        moved = self.engine.player_actions.move(1, 0)
        self.assertTrue(moved, "stairs must carry you down")
        self.assertIs(self.engine.current_dungeon, top.level_below)
        self.assertEqual(
            self.player.metadata.get("max_dungeon_depth"), 2)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("[Collection]", log)

    def test_tab_climbs_before_exiting(self):
        top = self._enter()
        self.engine.current_dungeon = top.level_below
        msg = self.engine.exit_dungeon()
        self.assertIn("climb", msg.lower())
        self.assertIs(self.engine.current_dungeon, top)
        msg = self.engine.exit_dungeon()
        self.assertIn("emerge", msg.lower())
        self.assertIsNone(self.engine.current_dungeon)

    def test_cross_floor_monsters_not_targetable(self):
        top = self._enter()
        deep = top.level_below
        deep_monster = next(n for n in
                            self.engine.npc_manager.npcs.values()
                            if n.metadata.get("zone") == deep.name)
        self.engine.current_dungeon = top
        self.player.position = top.exit_pos
        ok, why = self.engine.targeting.can_hit(deep_monster)
        self.assertFalse(ok, "monsters a floor below are unreal")

    def test_stack_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        top = self._enter()
        name = next(iter(self.engine.dungeons))
        self.engine.exit_dungeon()
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="delve")
            self.engine.dungeons = {}
            self.assertTrue(sm.load(self.engine, name="delve"))
            loaded = self.engine.dungeons[name]
            self.assertIsNotNone(loaded.level_below,
                                 "the stack must persist")
            self.assertEqual(loaded.stairs_down,
                             top.stairs_down)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
