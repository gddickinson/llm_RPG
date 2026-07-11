"""Player roster & controllers (M.1) — the "who is acting" keystone.

The engine has always had a single `engine.player`. Multiplayer and
agent-driven characters need a ROSTER of controllable heroes, each with
a CONTROLLER — a human at the keyboard, or (M.2) an autonomous agent —
and one of them ACTIVE (the character `engine.player` points at). This
is the abstraction everything else builds on; it does not itself DRIVE
anyone (that is M.2) or sync over a wire (M.4).

It's deliberately additive: `engine.player` stays the active character,
so every existing call keeps working, and the roster tracks the wider
set alongside it. Controllers are keyed by character id and each
character's controller kind rides on `character.metadata['controller']`,
so the roster survives a save/load (which rebuilds the player object)
with no new save-format work.
"""

HUMAN = "human"
AGENT = "agent"


class PlayerController:
    """Who drives a character: a human, or (M.2) an autonomous agent."""

    def __init__(self, kind: str = HUMAN, name: str = "Player"):
        self.kind = kind
        self.name = name

    @property
    def is_human(self) -> bool:
        return self.kind == HUMAN

    @property
    def is_agent(self) -> bool:
        return self.kind == AGENT

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name}

    @staticmethod
    def from_dict(d: dict) -> "PlayerController":
        return PlayerController(d.get("kind", HUMAN),
                                d.get("name", "Player"))

    def __repr__(self):
        return f"PlayerController({self.kind}, {self.name!r})"


class PlayerRoster:
    def __init__(self, engine):
        self.engine = engine
        self._by_id = {}          # character id -> live Character
        self._controllers = {}    # character id -> PlayerController

    # ---- internals ----------------------------------------------

    def _register(self, char, controller: PlayerController):
        self._by_id[char.id] = char
        self._controllers[char.id] = controller
        try:
            char.metadata["controller"] = controller.kind
        except Exception:
            pass
        return controller

    def _sync_active(self) -> None:
        """Make sure the current `engine.player` is in the roster —
        and, after a load, that we hold the NEW object for its id."""
        p = getattr(self.engine, "player", None)
        if p is None:
            return
        if self._by_id.get(p.id) is not p:
            kind = (getattr(p, "metadata", {}) or {}).get(
                "controller", HUMAN)
            self._register(p, PlayerController(
                kind, getattr(p, "name", "Player")))

    # ---- api ----------------------------------------------------

    def add(self, character, controller: PlayerController = None):
        """Register a controllable character (defaults to a human)."""
        self._sync_active()          # keep the standing player on the roster
        return self._register(character, controller or PlayerController())

    @property
    def active(self):
        return self.engine.player

    @property
    def characters(self) -> list:
        self._sync_active()
        return list(self._by_id.values())

    def controller_for(self, character):
        self._sync_active()
        return self._controllers.get(character.id)

    def is_controlled(self, character) -> bool:
        self._sync_active()
        return character.id in self._controllers

    def set_active(self, character):
        """Hand control to another roster character — `engine.player`
        follows, so every existing system now acts as that hero."""
        self._sync_active()          # register the character we're leaving
        if character.id not in self._by_id and \
                character is not self.engine.player:
            raise KeyError(f"{getattr(character, 'id', '?')} "
                           f"is not in the roster")
        self.engine.player = character
        self._sync_active()
        return character

    def humans(self) -> list:
        return [c for c in self.characters
                if self._controllers[c.id].is_human]

    def agents(self) -> list:
        return [c for c in self.characters
                if self._controllers[c.id].is_agent]
