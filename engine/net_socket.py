"""Networked play — the TCP wire (M.4b).

The thin, replaceable transport over `engine/net_server.py`. Everything
interesting (identity, validation, the world clock) already lives in
`NetServer`/`GameServer`; this file is just a pump:

    recv bytes -> FrameDecoder -> NetServer.on_message -> encode -> send

`NetHost` runs a threaded TCP server hosting ONE `NetServer`; each
connection is a client, and an optional background ticker advances the
shared world on a schedule and broadcasts a snapshot to everyone.
`NetClient` is the other end — connect, join, ship intents, read the
latest snapshot. The single-process game never imports this; it is opt-
in networking (`--serve` / a future menu) layered on the same engine.

Kept deliberately small and dependency-light (stdlib `socket` /
`socketserver` / `threading`). The message logic is unit-tested in
`net_server`; the socket round-trip has an end-to-end smoke test that
skips where a sandbox forbids binding a port.
"""

import logging
import socket
import socketserver
import threading
import time

from engine import net_server as proto

logger = logging.getLogger("llm_rpg.net_socket")

RECV = 4096
POLL_TIMEOUT = 0.5


class _Handler(socketserver.BaseRequestHandler):
    """One connected client: decode frames, dispatch, reply."""

    def handle(self):
        srv = self.server
        cid = "%s:%d" % self.client_address
        srv.net.on_connect(cid)
        with srv.lock:
            srv.conns[cid] = self.request
        dec = proto.FrameDecoder()
        self.request.settimeout(POLL_TIMEOUT)
        try:
            while not srv.stopping:
                try:
                    data = self.request.recv(RECV)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not data:
                    break
                for msg in dec.feed(data):
                    with srv.lock:
                        resp = srv.net.on_message(cid, msg)
                    try:
                        self.request.sendall(proto.encode(resp))
                    except OSError:
                        break
        finally:
            with srv.lock:
                srv.conns.pop(cid, None)
                srv.net.on_disconnect(cid)


class _RPGServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, net):
        self.net = net
        self.conns = {}                 # connection id -> socket
        self.lock = threading.RLock()
        self.stopping = False
        super().__init__(addr, _Handler)


class NetHost:
    """A running server: a threaded TCP listener + an optional ticker."""

    def __init__(self, net, host="127.0.0.1", port=0,
                 tick_interval=None):
        self.net = net
        self.tick_interval = tick_interval
        self._srv = _RPGServer((host, port), net)
        self._serve_thread = None
        self._tick_thread = None

    @property
    def address(self):
        """The bound (host, port) — the port is real even if 0 requested."""
        return self._srv.server_address

    def start(self) -> "NetHost":
        self._serve_thread = threading.Thread(
            target=self._srv.serve_forever, name="nethost-serve",
            daemon=True)
        self._serve_thread.start()
        if self.tick_interval:
            self._tick_thread = threading.Thread(
                target=self._tick_loop, name="nethost-tick", daemon=True)
            self._tick_thread.start()
        return self

    def _tick_loop(self):
        while not self._srv.stopping:
            time.sleep(self.tick_interval)
            if self._srv.stopping:
                break
            try:
                frame = self.net.tick_and_broadcast()
            except Exception as e:                       # pragma: no cover
                logger.warning(f"tick: {e}")
                continue
            self.broadcast(frame)

    def broadcast(self, frame: dict) -> int:
        """Push one frame to every connected client; returns the count
        reached."""
        data = proto.encode(frame)
        sent = 0
        with self._srv.lock:
            for sock in list(self._srv.conns.values()):
                try:
                    sock.sendall(data)
                    sent += 1
                except OSError:
                    pass
        return sent

    def stop(self):
        self._srv.stopping = True
        try:
            self._srv.shutdown()
        except Exception:
            pass
        try:
            self._srv.server_close()
        except Exception:
            pass


class NetClient:
    """The thin client end: connect, join, ship intents, read snapshots.

    Synchronous request/reply — each send reads back one frame — which
    keeps the API and the tests simple. When a host runs a background
    ticker, use `recv` to drain pushed snapshots.
    """

    def __init__(self, host, port, timeout=2.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._dec = proto.FrameDecoder()
        self._inbox = []
        self.player = None
        self.snapshot = None

    def _send(self, msg: dict) -> None:
        self._sock.sendall(proto.encode(msg))

    def recv(self) -> dict:
        """Block for the next whole message; caches player/snapshot off it."""
        while not self._inbox:
            data = self._sock.recv(RECV)
            if not data:
                raise ConnectionError("host closed the connection")
            self._inbox.extend(self._dec.feed(data))
        msg = self._inbox.pop(0)
        snap = msg.get("snapshot")
        if snap is not None:
            self.snapshot = snap
        if msg.get("t") == proto.WELCOME:
            self.player = msg.get("player")
        return msg

    def join(self, player=None, name=None, kind="human") -> dict:
        self._send(proto.msg_join(player, name, kind))
        return self.recv()

    def intent(self, verb: str, **args) -> dict:
        self._send(proto.msg_intent(verb, self.player, **args))
        return self.recv()

    def poll(self) -> dict:
        self._send(proto.msg_poll())
        return self.recv()

    def leave(self) -> dict:
        self._send(proto.msg_leave())
        return self.recv()

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass
