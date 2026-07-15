"""Networked play — the authoritative session (M.4a).

Proves the client<->world contract independent of any wire: intents
serialise, `join` seats heroes, `submit` applies actions authoritatively
WITHOUT ticking the world, `tick` is the server's own clock, and
`snapshot` is a JSON view clients can read.
"""

import json
import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine            # noqa: E402
from engine.netplay import Intent, GameServer, INTENT_VERBS  # noqa: E402
from engine.player_roster import AGENT               # noqa: E402
from world.monsters import build_monster             # noqa: E402


class TestIntent(unittest.TestCase):
    def test_round_trip_through_json(self):
        i = Intent("hero_2", "move", {"dx": 1, "dy": -1})
        wire = json.dumps(i.to_dict())          # crosses a socket unchanged
        back = Intent.from_dict(json.loads(wire))
        self.assertEqual(back.player, "hero_2")
        self.assertEqual(back.verb, "move")
        self.assertEqual(back.args, {"dx": 1, "dy": -1})

    def test_defaults_are_safe(self):
        i = Intent.from_dict({})
        self.assertEqual(i.verb, "wait")
        self.assertEqual(i.args, {})


class TestServer(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.server = GameServer(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    # ---- membership --------------------------------------------------

    def test_host_binds_to_active_player(self):
        host = self.server.join("host", "George")
        self.assertIs(host, self.engine.player)
        self.assertTrue(self.engine.roster.is_controlled(host))

    def test_join_seats_a_second_hero_in_the_world(self):
        px, py = self.engine.player.position
        hero = self.server.join("hero_2", "Remote", spawn=(px + 2, py))
        self.assertEqual(hero.id, "hero_2")
        self.assertIn(hero, self.engine.roster.characters)
        # a live body: in the NPC pool so it renders + saves
        self.assertIn("hero_2", self.engine.npc_manager.npcs)
        self.assertTrue(hero.metadata.get("player_char"))

    def test_join_is_idempotent(self):
        a = self.server.join("hero_2", "Remote")
        b = self.server.join("hero_2", "Remote")
        self.assertIs(a, b)

    def test_join_agent_controller(self):
        self.server.join("bot", "Botfriend", kind=AGENT)
        ctrl = self.engine.roster.controller_for(self.server._resolve("bot"))
        self.assertTrue(ctrl.is_agent)

    # ---- submit is authoritative & does NOT tick the world ----------

    def test_move_applies_without_ticking(self):
        self.server.join("host")
        tc0 = self.engine.turn_counter
        moved = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            r = self.server.submit(Intent("player", "move",
                                          {"dx": dx, "dy": dy}))
            if r["ok"]:
                moved = True
                break
        self.assertTrue(moved, "some direction was walkable")
        self.assertEqual(self.engine.turn_counter, tc0,
                         "submit applies the action but does not tick")

    def test_submit_accepts_a_plain_dict(self):
        self.server.join("host")
        r = self.server.submit({"player": "player", "verb": "wait"})
        self.assertTrue(r["ok"])

    def test_unknown_verb_is_rejected(self):
        self.server.join("host")
        r = self.server.submit(Intent("player", "explode"))
        self.assertFalse(r["ok"])

    def test_unknown_player_is_rejected(self):
        r = self.server.submit(Intent("ghost", "wait"))
        self.assertFalse(r["ok"])

    def test_say_writes_one_event(self):
        self.server.join("host")
        r = self.server.submit(Intent("player", "say", {"text": "hail!"}))
        self.assertTrue(r["ok"])
        recent = " ".join(self.engine.memory_manager.get_recent_history(5))
        self.assertIn("hail!", recent)

    def test_attack_damages_an_adjacent_foe(self):
        self.server.join("host")
        px, py = self.engine.player.position
        wolf = build_monster("wolf", (px + 1, py))
        self.engine.npc_manager.add_npc(wolf)
        hp0 = wolf.hp
        for _ in range(12):                    # a d20 swing can miss
            if wolf.hp < hp0:
                break
            self.server.submit(Intent("player", "attack", {"target": wolf.name}))
        self.assertLess(wolf.hp, hp0)

    # ---- the world clock --------------------------------------------

    def test_tick_advances_the_shared_world(self):
        self.server.join("host")
        tc0 = self.engine.turn_counter
        tc1 = self.server.tick()
        self.assertEqual(tc1, tc0 + 1)
        self.assertEqual(self.engine.turn_counter, tc0 + 1)

    def test_two_heroes_act_independently(self):
        self.server.join("host")
        px, py = self.engine.player.position
        h2 = self.server.join("hero_2", "Remote", spawn=(px + 3, py))
        p2_0 = tuple(h2.position)
        moved_each = 0
        for who, start in (("player", tuple(self.engine.player.position)),
                           ("hero_2", p2_0)):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                r = self.server.submit(Intent(who, "move",
                                              {"dx": dx, "dy": dy}))
                if r["ok"]:
                    moved_each += 1
                    break
        self.assertEqual(moved_each, 2, "each hero moved on its own intent")

    # ---- snapshot ----------------------------------------------------

    def test_snapshot_is_json_serialisable(self):
        self.server.join("host")
        self.server.join("hero_2", "Remote")
        snap = self.server.snapshot()
        blob = json.dumps(snap)                 # must not raise
        self.assertIn("players", snap)
        ids = {p["id"] for p in snap["players"]}
        self.assertIn("player", ids)
        self.assertIn("hero_2", ids)
        self.assertIsInstance(snap["tick"], int)
        self.assertGreater(len(blob), 0)

    def test_snapshot_reports_controllers(self):
        self.server.join("host")
        self.server.join("bot", kind=AGENT)
        snap = self.server.snapshot()
        bot = next(p for p in snap["players"] if p["id"] == "bot")
        self.assertEqual(bot["controller"], AGENT)

    # ---- disconnect --------------------------------------------------

    def test_leave_hands_the_hero_to_an_agent(self):
        host = self.server.join("host")
        self.assertTrue(self.server.leave("player"))
        self.assertTrue(self.engine.roster.is_away(host))

    def test_verbs_are_whitelisted(self):
        self.assertEqual(set(INTENT_VERBS), {"move", "attack", "say", "wait"})


if __name__ == "__main__":
    unittest.main()
