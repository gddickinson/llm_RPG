"""Terrain crossings (P11.1 contract) + earned teleports (P2.8)."""

import unittest

from engine.game_engine import GameEngine
from engine.skill_progression import (add_skill_xp, total_xp_for_level,
                                      get_skill_xp)
from engine.travel import TELEPORT_TOLL
from world.world_map import TerrainType


class _FixedRng:
    def __init__(self, value):
        self.value = value

    def randint(self, a, b):
        return self.value


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

    def test_failed_climb_blocks_and_logs(self):
        step = _adjacent_to(self.engine, TerrainType.MOUNTAIN)
        if step is None:
            self.skipTest("no reachable mountain edge")
        self.engine.traversal.rng = _FixedRng(1)   # doomed roll
        before = self.player.position
        moved = self.engine.move_player(*step)
        self.assertFalse(moved)
        self.assertEqual(self.player.position, before)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("grip", log.lower())

    def test_high_agility_cannot_fail_the_climb(self):
        step = _adjacent_to(self.engine, TerrainType.MOUNTAIN)
        if step is None:
            self.skipTest("no reachable mountain edge")
        add_skill_xp(self.player, "agility", total_xp_for_level(15))
        self.engine.traversal.rng = _FixedRng(1)   # worst roll
        xp_before = get_skill_xp(self.player, "agility")
        target = (self.player.position[0] + step[0],
                  self.player.position[1] + step[1])
        moved = self.engine.move_player(*step)
        self.assertTrue(moved, "mastery is certainty")
        self.assertEqual(self.player.position, target)
        self.assertGreater(get_skill_xp(self.player, "agility"),
                           xp_before)

    def test_shore_water_is_wadeable_by_anyone(self):
        step = _adjacent_to(self.engine, TerrainType.WATER)
        if step is None:
            self.skipTest("no reachable shoreline")
        self.engine.traversal.rng = _FixedRng(1)   # wading never rolls
        n_before = len(self.engine.memory_manager.game_history)
        self.assertTrue(self.engine.move_player(*step))
        # scan every beat this move produced — ambient world beats (a distant
        # collapse, an NPC's world spell) can crowd a small tail window
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[n_before:])
        self.assertIn("wade", log.lower())


class TestTeleports(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.travel = self.engine.travel_system
        # these exercise teleport MECHANICS (landing/cooldown/toll), not the
        # waystone-only gate — bypass it so they teleport from anywhere; the
        # gate itself is covered by test_exit_teleport_gating.
        self.travel.at_station = lambda: True

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

    def test_teleport_never_lands_on_a_building(self):
        # Oakvale's centre IS a building tile — the player must not be
        # stranded on it (2026-07-12e trap bug)
        from world.world_map import TerrainType
        self.travel.teleport(0)
        x, y = self.player.position
        self.assertNotEqual(self.engine.world.map.terrain[y][x],
                            TerrainType.BUILDING)

    def test_safe_landing_avoids_a_forced_building(self):
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        wmap.terrain[10][10] = TerrainType.BUILDING
        land = self.travel._safe_landing((10, 10))
        self.assertNotEqual(wmap.terrain[land[1]][land[0]],
                            TerrainType.BUILDING)

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
