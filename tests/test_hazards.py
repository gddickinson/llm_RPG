"""Environmental hazard tests (P11.2): sweeps, drowning, tumbles."""

import unittest

from engine.game_engine import GameEngine
from engine.hazards import flow_at, water_hazard_tick
from world.world_map import TerrainType


class _FixedRng:
    def __init__(self, value):
        self.value = value

    def randint(self, a, b):
        return self.value

    def choice(self, seq):
        return seq[0]


class TestHazards(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.player = self.engine.player
        self.ox, self.oy = self.wmap.width - 16, self.wmap.height - 10
        for y in range(self.oy - 4, self.oy + 6):
            for x in range(self.ox - 4, self.ox + 12):
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

    def _river(self):
        """An 11-long, 3-wide river running east. Middle row is deep."""
        for dy in (-1, 0, 1):
            for dx in range(11):
                self.wmap.terrain[self.oy + dy][self.ox + dx] = \
                    TerrainType.WATER
        return self.ox + 5, self.oy      # a deep mid-channel tile

    def _lake(self):
        """A 5x5 still pool south of the staging row."""
        for dy in range(5):
            for dx in range(5):
                self.wmap.terrain[self.oy + dy][self.ox + dx] = \
                    TerrainType.WATER
        return self.ox + 2, self.oy + 2   # deep center

    def test_rivers_flow_lakes_do_not(self):
        x, y = self._river()
        self.assertEqual(flow_at(self.engine, x, y), (1, 0),
                         "long water runs east")
        self.engine2 = self.engine     # reuse map for the lake
        for dy in (-1, 0, 1):          # clear the river first
            for dx in range(11):
                self.wmap.terrain[self.oy + dy][self.ox + dx] = \
                    TerrainType.GRASS
        lx, ly = self._lake()
        self.assertIsNone(flow_at(self.engine, lx, ly),
                          "round water is slack")

    def test_treading_water_is_safe(self):
        x, y = self._river()
        self._put_player(x, y)
        self.engine.traversal.rng = _FixedRng(20)
        hp0 = self.player.hp
        water_hazard_tick(self.engine)
        self.assertEqual(self.player.hp, hp0)
        self.assertEqual(self.player.position, (x, y))

    def test_failed_struggle_sweeps_downstream(self):
        x, y = self._river()
        self._put_player(x, y)
        self.player.hp = self.player.max_hp
        self.engine.traversal.rng = _FixedRng(1)
        water_hazard_tick(self.engine)
        self.assertGreater(self.player.position[0], x,
                           "the current must carry you east")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("sweeps you downstream", log)

    def test_drowning_escalates_but_never_kills(self):
        x, y = self._lake()
        self._put_player(x, y)
        self.player.hp = self.player.max_hp
        self.engine.traversal.rng = _FixedRng(1)
        water_hazard_tick(self.engine)
        hp_after_one = self.player.hp
        dmg1 = self.player.max_hp - hp_after_one
        self.assertGreater(dmg1, 0)
        # escalation: the second failing turn hurts more (unless
        # already washed ashore)
        if self.wmap.terrain[self.player.position[1]] \
                [self.player.position[0]] == TerrainType.WATER:
            water_hazard_tick(self.engine)
            dmg2 = hp_after_one - self.player.hp
            self.assertGreater(dmg2, dmg1)
        # drown to the floor: never dies
        for _ in range(20):
            if self.wmap.terrain[self.player.position[1]] \
                    [self.player.position[0]] != TerrainType.WATER:
                break
            water_hazard_tick(self.engine)
        self.assertGreaterEqual(self.player.hp, 1,
                                "water maims; the story kills")

    def test_washed_ashore_on_dry_land_minus_one_item(self):
        x, y = self._lake()
        self._put_player(x, y)
        from items.item_registry import create_item
        self.player.inventory = [create_item("bread")]
        self.player.hp = 3
        self.engine.traversal.rng = _FixedRng(1)
        for _ in range(10):
            if self.wmap.terrain[self.player.position[1]] \
                    [self.player.position[0]] != TerrainType.WATER:
                break
            water_hazard_tick(self.engine)
        px, py = self.player.position
        self.assertNotEqual(self.wmap.terrain[py][px],
                            TerrainType.WATER,
                            "the river spits you out")
        self.assertEqual(self.player.inventory, [],
                         "the river keeps a souvenir")
        self.assertEqual(self.player.metadata.get("fatigue"), 100)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("washed ashore", log.lower())

    def test_bad_climb_fail_tumbles_off_the_rock(self):
        # standing on rock, badly failing the next climb
        self.wmap.terrain[self.oy][self.ox] = TerrainType.MOUNTAIN
        self.wmap.terrain[self.oy][self.ox + 1] = TerrainType.MOUNTAIN
        self._put_player(self.ox, self.oy)
        self.player.hp = self.player.max_hp
        self.engine.traversal.rng = _FixedRng(1)
        msg = self.engine.traversal.attempt_cross(self.ox + 1, self.oy)
        self.assertIsNotNone(msg)
        px, py = self.player.position
        self.assertNotEqual(self.wmap.terrain[py][px],
                            TerrainType.MOUNTAIN,
                            "a bad fall takes you off the face")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("tumble", log.lower())

    def test_deep_water_warning_on_the_hint_bar(self):
        x, y = self._river()
        self._put_player(x, y)
        from ui.hints import context_hints
        hints = context_hints(self.engine)
        joined = " ".join(hints).lower()
        self.assertIn("deep water", joined)
        self.assertIn("current", joined)


if __name__ == "__main__":
    unittest.main()
