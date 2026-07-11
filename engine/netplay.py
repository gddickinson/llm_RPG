"""Networked play — the authoritative session (M.4a).

M.4 is networked multiplayer: heroes on different machines sharing one
world. The hard, replaceable part is the wire (sockets, threads) — the
DURABLE part is the *contract* between a client and the world, and that
is what this module nails down, transport-free and fully testable:

  * an **Intent** — the ONLY thing a client may send: a whitelisted
    verb (move / attack / say / wait) naming which hero acts and how.
    It serialises to plain JSON, so the same object crosses a socket
    unchanged (M.4b) as travels between two objects in a test.

  * a **GameServer** — the authoritative session that OWNS the engine.
    Clients never touch the engine; they `join` (a hero enters the
    roster + world), `submit` intents (validated, then applied through
    the SAME player-action route a human uses, acting AS that hero —
    but WITHOUT ticking the world), and read `snapshot`s (a serialisable
    view of every hero + nearby NPC). The server alone drives the world
    clock via `tick`, so N players' actions resolve against one ordered
    timeline instead of each move cascading a turn.

This is the M.4 keystone the way M.1 was the "who is acting" keystone:
once intents flow authoritatively and snapshots come back, bolting on a
socket transport that ships `Intent.to_dict()` up and `snapshot()` down
is a thin, separable layer (M.4b, noted in the plan).
"""

import logging

from engine.agent_controller import acting_as
from engine.player_roster import PlayerController, HUMAN

logger = logging.getLogger("llm_rpg.netplay")

# The whitelist — a client may ask for nothing else. Everything the
# engine can do to the world is reachable only through one of these.
INTENT_VERBS = ("move", "attack", "say", "wait")


class Intent:
    """A single client request: hero `player` wants to do `verb`.

    Pure data — `to_dict`/`from_dict` round-trip through JSON so the
    identical object crosses a wire or a function call.
    """

    __slots__ = ("player", "verb", "args")

    def __init__(self, player: str, verb: str, args: dict = None):
        self.player = player          # the acting hero's character id
        self.verb = verb
        self.args = dict(args or {})

    def to_dict(self) -> dict:
        return {"player": self.player, "verb": self.verb,
                "args": dict(self.args)}

    @staticmethod
    def from_dict(d: dict) -> "Intent":
        return Intent(d.get("player", ""), d.get("verb", "wait"),
                      d.get("args") or {})

    def __repr__(self):
        return f"Intent({self.player!r}, {self.verb!r}, {self.args!r})"


class GameServer:
    """Authoritative session: owns one engine, serves many heroes."""

    def __init__(self, engine):
        self.engine = engine

    # ---- membership --------------------------------------------------

    def _resolve(self, player_id):
        """The live Character for a joined hero id, or None."""
        roster = getattr(self.engine, "roster", None)
        if roster is None:
            return None
        for c in roster.characters:
            if getattr(c, "id", None) == player_id:
                return c
        return None

    def join(self, player_id: str, name: str = None, kind: str = HUMAN,
             spawn=None):
        """Bring a hero into the session.

        The host (`player_id` == the standing player's id, or "host")
        binds to `engine.player`; any other id mints a fresh hero, adds
        it to the roster (which places it live in the world), and hands
        it the given controller — human at a remote keyboard, or an
        M.2 agent.
        """
        eng = self.engine
        host = getattr(eng, "player", None)
        if host is not None and player_id in ("host", host.id):
            eng.roster.add(host, PlayerController(kind, name or host.name),
                           place=False)
            return host

        existing = self._resolve(player_id)
        if existing is not None:
            return existing

        from engine.demo_setup import create_default_player
        hero = create_default_player()
        hero.id = player_id
        hero.name = name or player_id
        if spawn is not None:
            hero.position = tuple(spawn)
        elif host is not None:
            hero.position = tuple(host.position)
        eng.roster.add(hero, PlayerController(kind, hero.name))
        return hero

    def leave(self, player_id: str) -> bool:
        """A client disconnects — hand its hero to an agent so it keeps
        living rather than freezing (reuses the M.3 away path)."""
        char = self._resolve(player_id)
        if char is None:
            return False
        ctrl = self.engine.roster.controller_for(char)
        if ctrl is not None and ctrl.is_human:
            self.engine.roster.set_away(char, True)
        return True

    # ---- the authoritative apply ------------------------------------

    def submit(self, intent) -> dict:
        """Validate and apply ONE intent against the world.

        Applied through the real player-action API (acting AS the hero),
        but with the world clock pinned (`_advancing`) so the action
        lands without cascading a turn — the server ticks the world on
        its own schedule via `tick`. Returns a small result dict; never
        raises, so one bad client can't fault the session.
        """
        if isinstance(intent, dict):
            intent = Intent.from_dict(intent)
        if intent.verb not in INTENT_VERBS:
            return {"ok": False, "msg": f"unknown verb {intent.verb!r}"}
        char = self._resolve(intent.player)
        if char is None:
            return {"ok": False, "msg": "no such player"}

        eng = self.engine
        was = getattr(eng, "_advancing", False)
        eng._advancing = True          # apply the action, don't tick the world
        try:
            with acting_as(eng, char):
                return self._apply(eng, char, intent)
        except Exception as e:                       # pragma: no cover
            logger.warning(f"submit {intent.verb} for {intent.player}: {e}")
            return {"ok": False, "msg": "error"}
        finally:
            eng._advancing = was

    def _apply(self, eng, char, intent) -> dict:
        v = intent.verb
        a = intent.args
        if v == "wait":
            return {"ok": True, "msg": "waits"}
        if v == "move":
            dx, dy = int(a.get("dx", 0)), int(a.get("dy", 0))
            moved = eng.move_player(dx, dy)
            return {"ok": bool(moved),
                    "msg": "moved" if moved else "blocked",
                    "pos": list(char.position)}
        if v == "attack":
            msg = eng.attack_character(a.get("target", ""))
            return {"ok": True, "msg": msg or "attack"}
        if v == "say":
            text = str(a.get("text", ""))[:200]
            try:
                eng.memory_manager.add_event(f"{char.name}: {text}")
            except Exception:
                pass
            return {"ok": True, "msg": "said"}
        return {"ok": False, "msg": "unhandled"}      # pragma: no cover

    # ---- the world clock --------------------------------------------

    def tick(self) -> int:
        """Advance the shared world one authoritative step and return the
        new tick. Runs the full turn pipeline once (NPCs, needs, agents,
        hazards) for everyone — the server's heartbeat, not any one
        client's move."""
        self.engine.advance_turn()
        return self.engine.turn_counter

    # ---- the state clients read -------------------------------------

    def snapshot(self) -> dict:
        """A JSON-serialisable view of the shared world for clients: the
        world clock, every joined hero, and the active NPCs around them
        (bodies, not brains — no engine objects leak)."""
        eng = self.engine
        roster = getattr(eng, "roster", None)
        heroes = roster.characters if roster else [eng.player]
        hero_ids = {getattr(h, "id", None) for h in heroes}

        def cap(c, controller=None):
            d = {"id": c.id, "name": c.name,
                 "pos": list(getattr(c, "position", (0, 0)) or (0, 0)),
                 "hp": getattr(c, "hp", 0),
                 "max_hp": getattr(c, "max_hp", 0),
                 "alive": bool(getattr(c, "is_active", lambda: True)())}
            if controller is not None:
                d["controller"] = controller.kind
                d["away"] = bool(controller.away)
            return d

        players = [cap(h, roster.controller_for(h) if roster else None)
                   for h in heroes]
        npcs = []
        for n in eng.npc_manager.npcs.values():
            if getattr(n, "id", None) in hero_ids:
                continue
            if not n.is_active():
                continue
            npcs.append(cap(n))
        return {"tick": eng.turn_counter,
                "time": eng.world.get_formatted_time(),
                "players": players, "npcs": npcs}
