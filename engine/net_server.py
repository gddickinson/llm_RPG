"""Networked play — the message layer & dispatch (M.4b, transport-free).

M.4a fixed the client<->world *contract* (an `Intent` in, a `snapshot`
out, applied by an authoritative `GameServer`). This module wraps that
contract in a WIRE FORMAT and a DISPATCHER, still with no sockets in
sight, so both are unit-testable to the byte:

  * **framing** — newline-delimited JSON. `encode(msg)` -> bytes;
    `FrameDecoder` buffers a byte stream and yields whole messages,
    tolerating split frames, several frames in one read, and garbage.

  * **the message protocol** — a tiny tagged-union: clients send
    JOIN / INTENT / LEAVE / POLL; the server answers WELCOME / RESULT /
    SNAPSHOT / ERROR. Every message is a plain JSON dict.

  * **`NetServer`** — owns one `GameServer` and a table of connected
    clients. `on_connect` / `on_message` / `on_disconnect` translate
    wire messages into `GameServer` calls and back. It is authoritative
    about IDENTITY too: a client's intents are forced to act as the
    hero it joined as, so no client can puppet another's character.
    `tick_and_broadcast` advances the shared world and yields the one
    frame every client should receive.

The real socket loop (`engine/net_socket.py`) is a thin pump over this:
recv bytes -> `FrameDecoder` -> `on_message` -> `encode` -> send.
"""

import json
import logging

from engine.netplay import GameServer  # noqa: F401  (type clarity)

logger = logging.getLogger("llm_rpg.net_server")

# ---- message tags ---------------------------------------------------
# client -> server
JOIN = "join"
INTENT = "intent"
LEAVE = "leave"
POLL = "poll"
# server -> client
WELCOME = "welcome"
RESULT = "result"
SNAPSHOT = "snapshot"
ERROR = "error"


# ---- framing --------------------------------------------------------

def encode(msg: dict) -> bytes:
    """One message -> one newline-terminated JSON frame (bytes)."""
    return (json.dumps(msg) + "\n").encode("utf-8")


class FrameDecoder:
    """Turns an arbitrarily-chunked byte stream into whole JSON messages.

    Bytes arrive from a socket in any-sized pieces — half a frame, three
    frames, a frame split across two reads. `feed` buffers and returns
    every COMPLETE message so far; a line that isn't valid JSON comes
    back as an ERROR message rather than derailing the stream.
    """

    def __init__(self):
        self._buf = b""

    def feed(self, data: bytes) -> list:
        self._buf += data
        out = []
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line.decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                out.append({"t": ERROR, "msg": "bad frame"})
        return out


# ---- message constructors (thin, for clean call sites) --------------

def msg_join(player=None, name=None, kind="human") -> dict:
    return {"t": JOIN, "player": player, "name": name, "kind": kind}


def msg_intent(verb: str, player=None, **args) -> dict:
    return {"t": INTENT,
            "intent": {"player": player, "verb": verb, "args": args}}


def msg_leave() -> dict:
    return {"t": LEAVE}


def msg_poll() -> dict:
    return {"t": POLL}


# ---- the dispatcher -------------------------------------------------

class NetServer:
    """The message brain: wire messages in, wire messages out, one
    authoritative `GameServer` in the middle."""

    def __init__(self, game_server: GameServer):
        self.game = game_server
        self.clients = {}          # connection id -> joined hero id (or None)

    # -- connection lifecycle --------------------------------------

    def on_connect(self, client_id) -> None:
        self.clients[client_id] = None

    def on_disconnect(self, client_id):
        """A client drops: unregister it and hand its hero to an agent so
        the world doesn't freeze a body (the M.3 away path)."""
        player = self.clients.pop(client_id, None)
        if player:
            try:
                self.game.leave(player)
            except Exception as e:                       # pragma: no cover
                logger.warning(f"leave {player}: {e}")
        return player

    # -- one message ------------------------------------------------

    def on_message(self, client_id, msg: dict) -> dict:
        if client_id not in self.clients:                # tolerate no on_connect
            self.clients[client_id] = None
        t = msg.get("t")
        if t == JOIN:
            return self._do_join(client_id, msg)
        if t == INTENT:
            return self._do_intent(client_id, msg)
        if t == LEAVE:
            self.on_disconnect(client_id)
            return {"t": SNAPSHOT, "snapshot": self.game.snapshot()}
        if t == POLL:
            return {"t": SNAPSHOT, "snapshot": self.game.snapshot()}
        return {"t": ERROR, "msg": f"unknown message {t!r}"}

    def _do_join(self, client_id, msg) -> dict:
        pid = msg.get("player") or str(client_id)
        try:
            hero = self.game.join(pid, msg.get("name"),
                                  msg.get("kind", "human"))
        except Exception as e:                           # pragma: no cover
            logger.warning(f"join {pid}: {e}")
            return {"t": ERROR, "msg": "join failed"}
        self.clients[client_id] = hero.id
        return {"t": WELCOME, "player": hero.id,
                "snapshot": self.game.snapshot()}

    def _do_intent(self, client_id, msg) -> dict:
        pid = self.clients.get(client_id)
        if not pid:
            return {"t": ERROR, "msg": "join before acting"}
        intent = dict(msg.get("intent") or {})
        intent["player"] = pid            # authoritative: act as YOUR hero
        result = self.game.submit(intent)
        return {"t": RESULT, "result": result,
                "snapshot": self.game.snapshot()}

    # -- the world clock -------------------------------------------

    def tick_and_broadcast(self) -> dict:
        """Advance the shared world one step; return the frame the wire
        should push to every connected client."""
        self.game.tick()
        return {"t": SNAPSHOT, "snapshot": self.game.snapshot()}

    def connected_players(self) -> list:
        return [p for p in self.clients.values() if p]
