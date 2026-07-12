"""P31.1c — the tower guards defend.

A guard at a corner wall tower spots an approaching hostile from its height,
cries the alarm, and looses arrows down at it — ranged, over the wall.
"""

import unittest

from engine.game_engine import GameEngine
from engine import tower_defense as td
from world.monsters import build_monster
from world.world_map import TerrainType


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.tdf = self.engine.tower_defense
        # a LONE tower guard on clear ground, no other hostiles and none of
        # the real Oakvale corner towers in play (so the scenario is isolated)
        for nid in list(self.engine.npc_manager.npcs):
            n = self.engine.npc_manager.npcs[nid]
            meta = getattr(n, "metadata", {}) or {}
            if getattr(n.character_class, "value", "") in td._HOSTILE \
                    or meta.get("tower_guard"):
                self.engine.world.map.remove_character(n)
                self.engine.npc_manager.remove_npc(nid)
        self.gx, self.gy = 30, 30
        w = self.engine.world.map
        for yy in range(self.gy - td.TOWER_RANGE - 1, self.gy + 2):
            for xx in range(self.gx - 1, self.gx + td.TOWER_RANGE + 2):
                if 0 <= xx < w.width and 0 <= yy < w.height:
                    w.terrain[yy][xx] = TerrainType.GRASS
        self.guard = self._a_tower_guard(self.gx, self.gy)
        # stand the player within earshot so the tower's cries/arrows log
        w = self.engine.world.map
        w.remove_character(self.engine.player)
        self.engine.player.position = (self.gx, self.gy + 1)
        w.place_character(self.engine.player, *self.engine.player.position)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _a_tower_guard(self, x, y):
        from characters.character_types import CharacterClass
        g = self.engine.npc_manager.create_random_npc(
            char_class=CharacterClass.GUARD)
        g.metadata["tower_guard"] = [x, y]
        self.engine.world.map.remove_character(g)
        g.position = (x, y)
        self.engine.world.map.place_character(g, x, y)
        return g

    def _a_raider(self, dist):
        foe = build_monster("bandit", (self.gx, self.gy - dist))
        foe.hp = foe.max_hp = 99
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.remove_character(foe)
        foe.position = (self.gx, self.gy - dist)
        self.engine.world.map.place_character(foe, *foe.position)
        return foe

    def _log(self):
        return " ".join(str(e) for e in
                        self.engine.memory_manager.game_history)


class TestDefense(_Base):
    def test_a_raider_in_range_is_shot(self):
        foe = self._a_raider(dist=5)
        self.engine.combat_system.rng = _FixedRng(20)
        before = foe.hp
        self.tdf.update()
        self.assertLess(foe.hp, before, "the tower looses an arrow")

    def test_the_alarm_is_raised(self):
        self._a_raider(dist=5)
        self.tdf.update()
        self.assertIn("[Alarm]", self._log())

    def test_a_distant_raider_is_ignored(self):
        foe = self._a_raider(dist=td.TOWER_RANGE + 3)   # out of range
        before = foe.hp
        self.tdf.update()
        self.assertEqual(foe.hp, before)

    def test_no_hostiles_no_shots(self):
        self.assertEqual(self.tdf.update(), 0)

    def test_the_alarm_clears_when_the_coast_is(self):
        foe = self._a_raider(dist=5)
        self.tdf.update()
        self.assertTrue(self.guard.metadata.get("alarmed"))
        # the raider falls / leaves
        self.engine.world.map.remove_character(foe)
        self.engine.npc_manager.remove_npc(foe.id)
        self.tdf.update()
        self.assertFalse(self.guard.metadata.get("alarmed"))

    def test_a_missed_shot_still_reports(self):
        self._a_raider(dist=5)
        self.engine.combat_system.rng = _FixedRng(1)    # a miss
        self.tdf.update()
        self.assertIn("[Guard]", self._log())


class _FixedRng:
    def __init__(self, roll):
        self.roll = roll

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def random(self):
        return 0.5


if __name__ == "__main__":
    unittest.main()
