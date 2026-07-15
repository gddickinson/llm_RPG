"""Networked play — the wire (M.4b).

Two layers, both proven here: the transport-free message/dispatch layer
(framing + `NetServer`, fully deterministic) and the real TCP round-trip
(`NetHost`/`NetClient`, a synchronous smoke test that SKIPS where a
sandbox forbids binding a port).
"""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine            # noqa: E402
from engine.netplay import GameServer                # noqa: E402
from engine import net_server as proto               # noqa: E402
from engine.net_server import NetServer, FrameDecoder, encode  # noqa: E402


# ---- framing (pure) -------------------------------------------------

class TestFraming(unittest.TestCase):
    def test_encode_decode_round_trip(self):
        dec = FrameDecoder()
        got = dec.feed(encode({"t": "poll"}))
        self.assertEqual(got, [{"t": "poll"}])

    def test_several_frames_in_one_read(self):
        dec = FrameDecoder()
        blob = encode({"a": 1}) + encode({"b": 2}) + encode({"c": 3})
        self.assertEqual(dec.feed(blob), [{"a": 1}, {"b": 2}, {"c": 3}])

    def test_a_frame_split_across_reads(self):
        dec = FrameDecoder()
        raw = encode({"hello": "world"})
        self.assertEqual(dec.feed(raw[:5]), [])       # nothing whole yet
        self.assertEqual(dec.feed(raw[5:]), [{"hello": "world"}])

    def test_garbage_line_becomes_an_error_not_a_crash(self):
        dec = FrameDecoder()
        got = dec.feed(b"{not json}\n" + encode({"ok": True}))
        self.assertEqual(got[0]["t"], proto.ERROR)
        self.assertEqual(got[1], {"ok": True})

    def test_blank_lines_are_skipped(self):
        dec = FrameDecoder()
        self.assertEqual(dec.feed(b"\n\n"), [])


# ---- dispatch (transport-free) --------------------------------------

class TestNetServer(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.net = NetServer(GameServer(self.engine))

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_join_welcomes_with_a_snapshot(self):
        self.net.on_connect("c1")
        r = self.net.on_message("c1", proto.msg_join("host", "George"))
        self.assertEqual(r["t"], proto.WELCOME)
        self.assertEqual(r["player"], "player")
        self.assertIn("players", r["snapshot"])
        self.assertEqual(self.net.clients["c1"], "player")

    def test_intent_before_join_is_refused(self):
        self.net.on_connect("c1")
        r = self.net.on_message("c1", proto.msg_intent("wait"))
        self.assertEqual(r["t"], proto.ERROR)

    def test_intent_is_bound_to_your_own_hero(self):
        # c1 joins as the host; even if it lies about the player field in
        # its intent, the server forces the action onto c1's own hero.
        self.net.on_connect("c1")
        self.net.on_message("c1", proto.msg_join("host"))
        spoof = {"t": proto.INTENT,
                 "intent": {"player": "somebody_else", "verb": "wait"}}
        r = self.net.on_message("c1", spoof)
        self.assertEqual(r["t"], proto.RESULT)
        self.assertTrue(r["result"]["ok"])            # ran as 'player', not spoofed

    def test_poll_returns_a_snapshot(self):
        self.net.on_connect("c1")
        self.net.on_message("c1", proto.msg_join("host"))
        r = self.net.on_message("c1", proto.msg_poll())
        self.assertEqual(r["t"], proto.SNAPSHOT)
        self.assertIn("tick", r["snapshot"])

    def test_unknown_message_is_an_error(self):
        r = self.net.on_message("c1", {"t": "frobnicate"})
        self.assertEqual(r["t"], proto.ERROR)

    def test_two_clients_join_and_see_each_other(self):
        self.net.on_message("c1", proto.msg_join("host"))
        self.net.on_message("c2", proto.msg_join("hero_2", "Remote"))
        snap = self.net.on_message("c1", proto.msg_poll())["snapshot"]
        ids = {p["id"] for p in snap["players"]}
        self.assertIn("player", ids)
        self.assertIn("hero_2", ids)
        self.assertEqual(set(self.net.connected_players()),
                         {"player", "hero_2"})

    def test_disconnect_hands_the_hero_to_an_agent(self):
        self.net.on_message("c1", proto.msg_join("host"))
        self.net.on_disconnect("c1")
        self.assertNotIn("c1", self.net.clients)
        self.assertTrue(self.engine.roster.is_away(self.engine.player))

    def test_tick_and_broadcast_advances_the_world(self):
        self.net.on_message("c1", proto.msg_join("host"))
        tc0 = self.engine.turn_counter
        frame = self.net.tick_and_broadcast()
        self.assertEqual(frame["t"], proto.SNAPSHOT)
        self.assertEqual(self.engine.turn_counter, tc0 + 1)
        self.assertEqual(frame["snapshot"]["tick"], tc0 + 1)


# ---- the real TCP round-trip (skips if binding is forbidden) --------

class TestSocketRoundTrip(unittest.TestCase):
    def setUp(self):
        from engine.net_socket import NetHost
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.net = NetServer(GameServer(self.engine))
        try:
            self.host = NetHost(self.net, port=0).start()   # no ticker
        except OSError as e:                                 # sandboxed
            self.engine.end_game()
            self.skipTest(f"cannot bind a socket here: {e}")
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        try:
            self.host.stop()
        except Exception:
            pass
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _client(self):
        from engine.net_socket import NetClient
        host, port = self.host.address
        try:
            c = NetClient(host, port)
        except OSError as e:                                 # pragma: no cover
            self.skipTest(f"cannot connect here: {e}")
        self.clients.append(c)
        return c

    def test_join_over_the_wire(self):
        c = self._client()
        r = c.join("host", "George")
        self.assertEqual(r["t"], proto.WELCOME)
        self.assertEqual(c.player, "player")
        ids = {p["id"] for p in c.snapshot["players"]}
        self.assertIn("player", ids)

    def test_intent_and_poll_over_the_wire(self):
        c = self._client()
        c.join("host")
        r = c.intent("wait")
        self.assertEqual(r["t"], proto.RESULT)
        self.assertTrue(r["result"]["ok"])
        snap = c.poll()["snapshot"]
        self.assertIsInstance(snap["tick"], int)

    def test_two_clients_share_one_world(self):
        a = self._client()
        b = self._client()
        a.join("host")
        b.join("hero_2", "Remote")
        snap = a.poll()["snapshot"]
        ids = {p["id"] for p in snap["players"]}
        self.assertIn("player", ids)
        self.assertIn("hero_2", ids)

    def test_host_broadcast_reaches_a_connected_client(self):
        c = self._client()
        c.join("host")
        reached = self.host.broadcast({"t": proto.SNAPSHOT,
                                       "snapshot": self.net.game.snapshot()})
        self.assertGreaterEqual(reached, 1)
        msg = c.recv()                       # the pushed frame
        self.assertEqual(msg["t"], proto.SNAPSHOT)


if __name__ == "__main__":
    unittest.main()
