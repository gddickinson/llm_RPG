"""Agility shortcuts + earned teleports (P2.8)."""

import unittest

from engine.game_engine import GameEngine
from engine.skill_progression import (add_skill_xp, total_xp_for_level,
                                      get_skill_xp)
from engine.travel import CLIMB_LEVEL, SWIM_LEVEL, TELEPORT_TOLL
from world.world_map import TerrainType


def _adjacent_to(engine, terrain):
    """Place player on a passable tile adjacent to `terrain`."""
    wmap = engine.world.map
    passable = (TerrainType.GRASS, TerrainType.FOREST, TerrainType.ROAD)
    for y in range(1, wmap.height - 1):
        for x in range(1, wmap.width - 1):
            if wmap.get_terrain_at(x, y) != terrain:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if wmap.get_terrain_at(x + dx, y + dy) in passable:
                    engine.player.position = (x + dx, y + dy)
                    wmap.place_character(engine.player, x + dx, y + dy)
                    return (-dx, -dy)  # direction back toward the terrain
    return None


class TestShortcuts(unittest.TestCase):
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

    def test_mountain_blocks_low_agility(self):
        step = _adjacent_to(self.engine, TerrainType.MOUNTAIN)
        if step is None:
            self.skipTest("no reachable mountain edge")
        before = self.player.position
        moved = self.engine.move_player(*step)
        self.assertFalse(moved)
        self.assertEqual(self.player.position, before)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("Agility", log)

    def test_climb_with_high_agility(self):
        step = _adjacent_to(self.engine, TerrainType.MOUNTAIN)
        if step is None:
            self.skipTest("no reachable mountain edge")
        add_skill_xp(self.player, "agility",
                     total_xp_for_level(CLIMB_LEVEL))
        xp_before = get_skill_xp(self.player, "agility")
        target = (self.player.position[0] + step[0],
                  self.player.position[1] + step[1])
        moved = self.engine.move_player(*step)
        self.assertTrue(moved)
        self.assertEqual(self.player.position, target)
        self.assertGreater(get_skill_xp(self.player, "agility"), xp_before)

    def test_swim_needs_higher_level_than_climb(self):
        step = _adjacent_to(self.engine, TerrainType.WATER)
        if step is None:
            self.skipTest("no reachable shoreline")
        add_skill_xp(self.player, "agility",
                     total_xp_for_level(CLIMB_LEVEL))
        self.assertFalse(self.engine.move_player(*step),
                         "climb level must not allow swimming")
        add_skill_xp(self.player, "agility",
                     total_xp_for_level(SWIM_LEVEL))
        self.assertTrue(self.engine.move_player(*step))


class TestTeleports(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.travel = self.engine.travel_system

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_oakvale_always_unlocked_others_locked(self):
        dests = self.travel.destinations()
        by_key = {d["key"]: d for d in dests}
        self.assertTrue(by_key["oakvale"]["unlocked"])
        self.assertFalse(by_key["riverside"]["unlocked"])
        self.assertIn("diary", by_key["riverside"]["locked_reason"])

    def test_teleport_home_moves_player_and_sets_cooldown(self):
        self.player.position = (1, 1)
        msg = self.travel.teleport(0)
        self.assertIn("Oakvale", msg)
        self.assertNotEqual(self.player.position, (1, 1))
        self.assertGreater(self.travel.cooldown_remaining(), 0)
        # Second teleport blocked by cooldown
        msg2 = self.travel.teleport(0)
        self.assertIn("recover", msg2)

    def test_diary_unlocks_destination_with_toll(self):
        self.player.metadata.setdefault("diaries", {})["riverside"] = \
            ["easy"]
        dests = {d["key"]: d for d in self.travel.destinations()}
        self.assertTrue(dests["riverside"]["unlocked"])
        self.player.gold = TELEPORT_TOLL + 5
        idx = [d["key"] for d in self.travel.destinations()].index(
            "riverside")
        msg = self.travel.teleport(idx)
        self.assertIn("Riverside", msg)
        self.assertEqual(self.player.gold, 5, "toll should be charged")

    def test_locked_teleport_refused(self):
        idx = [d["key"] for d in self.travel.destinations()].index(
            "stonepine")
        msg = self.travel.teleport(idx)
        self.assertIn("locked", msg.lower())

    def test_cooldown_persists_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.travel.teleport(0)
        remaining = self.travel.cooldown_remaining()
        self.assertGreater(remaining, 0)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="t")
            self.player.metadata["teleport_ready_at"] = 0
            self.assertTrue(sm.load(self.engine, name="t"))
            self.assertGreater(
                self.engine.travel_system.cooldown_remaining(), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_overlay_lists_destinations(self):
        lines = self.travel.overlay_lines()
        text = "\n".join(lines)
        self.assertIn("Oakvale Village", text)
        self.assertIn("LOCKED", text)


if __name__ == "__main__":
    unittest.main()
