"""P32.1 — pursuit speed: a faster creature runs the hero down.

Every real turn a nearby hostile advances toward the player by its `speed`
(tiles/turn), decoupled from the throttled ambient AI. A wolf (1.5) closes the
gap; a shambler (0.6) falls behind; a plain foe (1.0) keeps pace; a fleeing or
broken creature doesn't chase; a caught creature holds adjacent.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_pursuit_"))

import unittest

from engine.game_engine import GameEngine
from engine import pursuit
from world.world_map import TerrainType
from world.monsters import build_monster


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        # a clear patch of grass around the player so nothing blocks a chase
        self.px, self.py = 30, 20
        self.engine.player.position = (self.px, self.py)
        self.wmap.remove_character(self.engine.player)
        for y in range(self.py - 14, self.py + 14):
            for x in range(self.px - 14, self.px + 14):
                if 0 <= x < self.wmap.width and 0 <= y < self.wmap.height:
                    self.wmap.terrain[y][x] = TerrainType.GRASS
        self.wmap.place_character(self.engine.player, self.px, self.py)
        self._clear_npcs()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _clear_npcs(self):
        for npc in list(self.engine.npc_manager.npcs.values()):
            self.wmap.remove_character(npc)
        self.engine.npc_manager.npcs.clear()

    def _spawn(self, template, pos, speed=None):
        foe = build_monster(template, pos)
        if speed is not None:
            foe.metadata["speed"] = speed
        self.engine.npc_manager.add_npc(foe)
        self.wmap.remove_character(foe)
        foe.position = pos
        self.wmap.place_character(foe, *pos)
        return foe

    def _dist(self, a):
        return max(abs(a.position[0] - self.px), abs(a.position[1] - self.py))


class TestSpeedData(_Base):
    def test_speed_helper_defaults_to_one(self):
        foe = self._spawn("bandit", (self.px + 8, self.py))
        # bandit has no speed field -> metadata default 1.0
        self.assertEqual(pursuit.creature_speed(foe), 1.0)

    def test_wolf_carries_its_template_speed(self):
        foe = self._spawn("wolf", (self.px + 8, self.py))
        self.assertGreater(pursuit.creature_speed(foe), 1.0)

    def test_bad_speed_falls_back(self):
        foe = self._spawn("wolf", (self.px + 8, self.py), speed="fast")
        self.assertEqual(pursuit.creature_speed(foe), 1.0)


class TestPursuit(_Base):
    def test_a_fast_creature_closes_the_gap(self):
        foe = self._spawn("wolf", (self.px + 8, self.py), speed=1.5)
        start = self._dist(foe)
        for _ in range(4):
            self.engine.pursuit.update()
        self.assertLess(self._dist(foe), start)

    def test_a_slow_creature_barely_gains(self):
        slow = self._spawn("restless_bones", (self.px + 8, self.py), speed=0.5)
        fast = self._spawn("wolf", (self.px + 8, self.py - 3), speed=1.5)
        for _ in range(4):
            self.engine.pursuit.update()
        # over the same window the fast one has gained far more ground
        self.assertGreater(self._dist(slow), self._dist(fast))

    def test_a_plain_creature_keeps_pace_but_cannot_gain_on_a_mover(self):
        # 1.0 gains exactly one tile a turn; a 1.5 pursuer from the same spot
        # ends up strictly closer, proving speed matters
        plain = self._spawn("bandit", (self.px + 9, self.py), speed=1.0)
        quick = self._spawn("wolf", (self.px + 9, self.py - 2), speed=1.6)
        for _ in range(4):
            self.engine.pursuit.update()
        self.assertLess(self._dist(quick), self._dist(plain))

    def test_holds_when_adjacent(self):
        foe = self._spawn("wolf", (self.px + 1, self.py), speed=2.0)
        for _ in range(5):
            self.engine.pursuit.update()
        # never steps onto the player; stays where it is (already inside standoff)
        self.assertEqual(self._dist(foe), 1)
        self.assertNotEqual(foe.position, (self.px, self.py))

    def test_stops_at_the_standoff_distance(self):
        # a fast closer settles at HOLD_DIST, it doesn't press onto your heels
        foe = self._spawn("wolf", (self.px + 8, self.py), speed=2.0)
        for _ in range(12):
            self.engine.pursuit.update()
        self.assertEqual(self._dist(foe), pursuit.HOLD_DIST)

    def test_a_distant_creature_is_ignored(self):
        foe = self._spawn("wolf", (self.px + 20, self.py), speed=2.0)
        start = self._dist(foe)
        self.engine.pursuit.update()
        self.assertEqual(self._dist(foe), start)   # beyond CHASE_RADIUS

    def test_a_fleeing_creature_does_not_chase(self):
        foe = self._spawn("goblin", (self.px + 6, self.py), speed=2.0)
        foe.metadata["behavior"] = {"flee_below": 0.9}
        foe.hp = 1                                   # below the flee threshold
        start = self._dist(foe)
        self.engine.pursuit.update()
        self.assertEqual(self._dist(foe), start)

    def test_a_broken_pack_member_does_not_chase(self):
        foe = self._spawn("wolf", (self.px + 6, self.py), speed=2.0)
        foe.metadata["pack_broken"] = True
        start = self._dist(foe)
        self.engine.pursuit.update()
        self.assertEqual(self._dist(foe), start)

    def test_a_dead_creature_does_not_chase(self):
        foe = self._spawn("wolf", (self.px + 6, self.py), speed=2.0)
        foe.hp = 0
        start = self._dist(foe)
        self.engine.pursuit.update()
        self.assertEqual(self._dist(foe), start)

    def test_a_civilian_is_not_a_pursuer(self):
        from characters.npc_manager import NPCManager  # noqa: F401
        villager = self._spawn("wolf", (self.px + 6, self.py), speed=2.0)
        # masquerade the class as a villager
        from characters.character_types import CharacterClass
        villager.character_class = CharacterClass("villager")
        start = self._dist(villager)
        self.engine.pursuit.update()
        self.assertEqual(self._dist(villager), start)


if __name__ == "__main__":
    unittest.main()
