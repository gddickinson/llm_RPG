"""Enemy AI behavior profiles (P5.1)."""

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from llm.providers.heuristic import HeuristicProvider


def _act(provider, monster, player_pos, in_view=True):
    world_state = {"current_location": "wilderness",
                   "time_of_day": "day",
                   "player_position": player_pos}
    visible = "player @" if in_view else "grass"
    return provider.get_npc_action(monster, world_state, [], visible)


class TestBehaviorProfiles(unittest.TestCase):
    def setUp(self):
        self.provider = HeuristicProvider(seed=42)

    def test_bandit_flees_at_low_hp(self):
        bandit = build_monster("bandit", (10, 10))
        bandit.hp = 3   # 3/14 < 0.35
        action = _act(self.provider, bandit, (12, 10))
        self.assertEqual(action["action"], "move")
        self.assertEqual(action["target"], "west",
                         "must run AWAY from the player to the east")
        self.assertIn("runs", action["dialog"])

    def test_bandit_fights_at_full_hp(self):
        bandit = build_monster("bandit", (10, 10))
        action = _act(self.provider, bandit, (12, 10))
        self.assertEqual(action["action"], "attack")

    def test_troll_returns_to_territory(self):
        troll = build_monster("wandering_troll", (20, 20))
        troll.position = (35, 20)   # 15 tiles from home > radius 8
        action = _act(self.provider, troll, (37, 20))
        self.assertEqual(action["action"], "move")
        self.assertEqual(action["target"], "west",
                         "must head back toward its lair")

    def test_bog_lurker_lies_in_ambush(self):
        lurker = build_monster("bog_lurker", (30, 30))
        # Player far away and unseen: motionless
        action = _act(self.provider, lurker, (40, 40), in_view=False)
        self.assertEqual(action["action"], "wait")
        # Player close: strikes
        action = _act(self.provider, lurker, (31, 30), in_view=True)
        self.assertEqual(action["action"], "attack")

    def test_wolf_howls_once_then_attacks(self):
        wolf = build_monster("wolf", (10, 10))
        first = _act(self.provider, wolf, (11, 10))
        self.assertEqual(first["action"], "howl")
        second = _act(self.provider, wolf, (11, 10))
        self.assertEqual(second["action"], "attack",
                         "howl fires once, then fight")

    def test_alerted_packmate_converges(self):
        wolf = build_monster("wolf", (10, 10))
        wolf.metadata["alert"] = [20, 10]
        action = _act(self.provider, wolf, (20, 10), in_view=False)
        self.assertEqual(action["action"], "move")
        self.assertEqual(action["target"], "east")

    def test_alert_clears_on_arrival(self):
        wolf = build_monster("wolf", (19, 10))
        wolf.metadata["alert"] = [20, 10]
        _act(self.provider, wolf, (25, 25), in_view=False)
        self.assertNotIn("alert", wolf.metadata)


class TestHowlIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_howl_alerts_nearby_packmates_only(self):
        px, py = self.engine.player.position
        howler = build_monster("wolf", (px + 2, py))
        near = build_monster("wolf", (px + 6, py))
        far = build_monster("wolf", (px + 30, py + 30))
        goblin = build_monster("goblin", (px + 3, py))
        for m in (howler, near, far, goblin):
            self.engine.npc_manager.add_npc(m)

        self.engine.action_router.process(
            howler, {"action": "howl", "target": "the pack",
                     "dialog": "", "thoughts": "", "emotion": "",
                     "goal_update": ""})

        self.assertEqual(near.metadata.get("alert"), [px, py])
        self.assertNotIn("alert", far.metadata,
                         "out-of-range packmates stay unaware")
        self.assertNotIn("alert", goblin.metadata,
                         "other species don't answer wolf howls")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("howl echoes", log)


if __name__ == "__main__":
    unittest.main()
