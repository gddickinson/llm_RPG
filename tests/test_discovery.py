"""Fog-of-war & discovery tests (P15.11)."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.discovery import (actor_hidden, can_witness, is_explored,
                              is_visible, reveal_around, update,
                              use_map_item, visible_set)
from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.monsters import build_monster
from world.world_map import TerrainType


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        # open ground around the player
        px, py = self.player.position
        for y in range(py - 6, py + 7):
            for x in range(px - 6, px + 7):
                if 0 <= x < self.wmap.width and 0 <= y < self.wmap.height:
                    self.wmap.terrain[y][x] = TerrainType.GRASS
        update(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_you_see_your_own_tile_not_the_far_corner(self):
        px, py = self.player.position
        self.assertTrue(is_visible(self.engine, px, py))
        self.assertFalse(is_visible(self.engine, 0, 0),
                         "the far corner is unseen at start")

    def test_the_start_view_is_not_the_whole_map(self):
        seen = len(visible_set(self.engine))
        self.assertLess(seen, self.wmap.width * self.wmap.height,
                        "the map is not known at start")
        self.assertGreater(seen, 0)

    def test_walking_reveals_and_remembers(self):
        far = (self.player.position[0] + 4, self.player.position[1])
        self.assertFalse(is_explored(self.engine, *far)
                         and not is_visible(self.engine, *far))
        # step toward it; it becomes explored, then stays explored
        self.engine.player_actions.move(1, 0)
        self.engine.player_actions.move(1, 0)
        px, py = self.player.position
        behind = (px - 2, py)
        self.assertTrue(is_explored(self.engine, *behind),
                        "tiles behind you are remembered")

    def test_mountains_block_sight(self):
        px, py = self.player.position
        self.wmap.terrain[py][px + 1] = TerrainType.MOUNTAIN
        update(self.engine)
        self.assertFalse(is_visible(self.engine, px + 5, py),
                         "you can't see past the mountain")

    def test_unseen_actors_are_hidden(self):
        # a wolf close enough to shoot, but a mountain hides it —
        # actor_hidden is what the renderer honors (unseen = undrawn)
        px, py = self.player.position
        self.wmap.terrain[py][px + 1] = TerrainType.MOUNTAIN
        spot = (px + 3, py)
        self.wmap.terrain[py][px + 3] = TerrainType.GRASS
        wolf = build_monster("wolf", spot)
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *spot)
        update(self.engine)
        self.assertTrue(actor_hidden(self.engine, wolf),
                        "the mountain hides it from view")
        # and a wolf in the open (west, no mountain) IS seen
        open_spot = (px - 2, py)
        wolf2 = build_monster("wolf", open_spot)
        self.engine.npc_manager.add_npc(wolf2)
        self.wmap.place_character(wolf2, *open_spot)
        update(self.engine)
        self.assertFalse(actor_hidden(self.engine, wolf2),
                         "the open ground shows it")

    def test_the_log_only_reports_what_you_see(self):
        px, py = self.player.position
        self.assertTrue(can_witness(self.engine, (px, py)))
        self.assertFalse(can_witness(self.engine, (0, 0)),
                         "a fight in the far corner is not news")

    def test_a_regional_map_charts_the_towns(self):
        # a town the player has NOT walked to yet (unexplored center)
        town = next(
            (l for l in self.engine.world.locations
             if ("Hamlet" in l.name or "Camp" in l.name)
             and not is_explored(
                 self.engine, l.x + l.width // 2,
                 l.y + l.height // 2)), None)
        if town is None:
            self.skipTest("every town already in view at start")
        cx, cy = town.x + town.width // 2, town.y + town.height // 2
        msg = use_map_item(self.engine, create_item("regional_map"))
        self.assertIn("charted", msg.lower())
        self.assertTrue(is_explored(self.engine, cx, cy),
                        "the map fixed the town in memory")

    def test_the_explorers_chart_reveals_all(self):
        use_map_item(self.engine, create_item("explorers_chart"))
        self.assertTrue(is_explored(self.engine, 0, 0))
        self.assertTrue(is_explored(
            self.engine, self.wmap.width - 1, self.wmap.height - 1))

    def test_farsight_charts_a_wide_disc(self):
        self.player.metadata["spells_known"] = ["farsight"]
        self.player.metadata["mana"] = 20
        self.player.metadata["max_mana"] = 20
        px, py = self.player.position
        far = (px, min(self.wmap.height - 1, py + 15))
        self.assertFalse(is_explored(self.engine, *far))
        self.engine.cast_spell("farsight")
        self.assertTrue(is_explored(self.engine, *far),
                        "the mind's eye charts the land")

    def test_explored_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        reveal_around(self.engine, 5, 5, radius=3)
        self.assertTrue(is_explored(self.engine, 5, 5))
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="fog")
            self.player.metadata["explored"] = set()
            self.assertTrue(sm.load(self.engine, name="fog"))
            self.assertTrue(is_explored(self.engine, 5, 5),
                            "the charted land persists")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
