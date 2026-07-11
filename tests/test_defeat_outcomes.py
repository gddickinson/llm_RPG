"""Failure-as-story defeat outcome tests (P4.7)."""

import unittest

from engine.game_engine import GameEngine
from engine.defeat import handle_player_defeat
from world.monsters import build_monster


class FixedRandom:
    """random.Random stand-in with a scripted .random() value."""
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class TestDefeatOutcomes(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        px, py = self.player.position
        self.wolf = build_monster("wolf", (px + 1, py))
        self.engine.npc_manager.add_npc(self.wolf)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_robbed_outcome(self):
        self.player.gold = 100
        self.player.metadata["bank"] = 500
        self.player.hp = 0
        survived, msg = handle_player_defeat(
            self.engine, self.wolf, rng=FixedRandom(0.5))
        self.assertTrue(survived)
        self.assertIn("lighter of purse", msg)
        self.assertEqual(self.player.gold, 70, "30% of carried gold gone")
        self.assertEqual(self.player.metadata["bank"], 500,
                         "banked gold must be untouchable")
        self.assertEqual(self.player.status, "alive")
        self.assertGreaterEqual(self.player.hp, 1)

    def test_left_for_dead_outcome(self):
        self.player.hp = 0
        pos = self.player.position
        t0 = self.engine.world.time
        survived, msg = handle_player_defeat(
            self.engine, self.wolf, rng=FixedRandom(0.9))
        self.assertTrue(survived)
        self.assertIn("alive", msg)
        self.assertEqual(self.player.position, pos)
        self.assertEqual(self.player.hp, 1)
        self.assertGreaterEqual(self.engine.world.time - t0, 6 * 60)
        self.assertGreaterEqual(self.player.metadata.get("hunger", 0), 75)

    def test_slain_outcome_on_bad_roll(self):
        survived, msg = handle_player_defeat(
            self.engine, self.wolf, rng=FixedRandom(0.05))
        self.assertFalse(survived)

    def test_dungeon_defeat_is_always_final(self):
        from world.dungeon import generate_dungeon
        self.engine.current_dungeon = generate_dungeon(seed=3)
        survived, _ = handle_player_defeat(
            self.engine, self.wolf, rng=FixedRandom(0.99))
        self.assertFalse(survived,
                         "no rescue from the bottom of a dungeon")
        self.engine.current_dungeon = None

    def test_combat_integration_survivable(self):
        """Lethal hit -> DYING -> stabilize -> story outcome (P12.4)."""
        self.engine._has_gui = True
        self.engine.combat_system.rng = FixedRandom(0.4)  # robbed leg
        self.engine.combat_system.rng.randint = lambda a, b: b
        self.player.hp = 1
        self.player.gold = 50
        msg = self.engine.combat_system._handle_defeat(
            self.wolf, self.player, damage=5)
        self.assertIn("DYING", msg)
        from engine.dying import dying_tick
        dying_tick(self.engine)      # nat 20 -> stabilized -> robbed
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-6:])
        self.assertIn("purse", log)
        self.assertFalse(self.engine.player_dead)
        self.assertTrue(self.engine.running)
        self.assertEqual(self.player.status, "alive")

    def test_combat_integration_final(self):
        self.engine._has_gui = True
        self.engine.combat_system.rng = FixedRandom(0.05)
        self.engine.combat_system.rng.randint = lambda a, b: a  # nat 1s
        self.player.hp = 1
        self.engine.combat_system._handle_defeat(
            self.wolf, self.player, damage=5)
        from engine.dying import dying_tick
        dying_tick(self.engine)      # +2 -> 3
        dying_tick(self.engine)      # -> 4: the full table, slain
        self.assertTrue(self.engine.player_dead)

    def test_victor_remembers(self):
        handle_player_defeat(self.engine, self.wolf,
                             rng=FixedRandom(0.5))
        self.assertTrue(any("defeated" in m.get("event", "")
                            for m in self.wolf.memories))

    def test_sanctuary_is_passable(self):
        from engine.defeat import _sanctuary_position
        from world.world_map import TerrainType
        x, y = _sanctuary_position(self.engine)
        wmap = self.engine.world.map
        self.assertTrue(0 <= x < wmap.width and 0 <= y < wmap.height)
        self.assertIn(wmap.get_terrain_at(x, y),
                      (TerrainType.GRASS, TerrainType.ROAD))


if __name__ == "__main__":
    unittest.main()
