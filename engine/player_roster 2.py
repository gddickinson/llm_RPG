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
        self.driver = None        # M.2 AgentController (agents only)
        self.away = False         # M.3 human stepped away -> agent drives
        self.away_home = None     # the spot to potter around while away

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

    def _place_in_world(self, character) -> None:
        """A non-active hero is a live world entity — put it in the NPC
        pool (so it renders + saves) and on the map (M.1b)."""
        eng = self.engine
        try:
            if character.id not in eng.npc_manager.npcs:
                eng.npc_manager.add_npc(character)
            if not getattr(character, "position", None):
                character.position = eng.player.position
            eng.world.map.place_character(character, *character.position)
        except Exception:
            pass

    def _take_from_world(self, character) -> None:
        """The character becoming active leaves the NPC pool (it is now
        THE player, rendered/handled specially)."""
        eng = self.engine
        try:
            eng.npc_manager.remove_npc(character.id)
            eng.world.map.remove_character(character)
        except Exception:
            pass

    def add(self, character, controller: PlayerController = None,
            place: bool = True):
        """Register a controllable character (defaults to a human) and,
        unless it's the active player, place it live in the world."""
        self._sync_active()          # keep the standing player on the roster
        self._register(character, controller or PlayerController())
        try:
            character.metadata["player_char"] = True
        except Exception:
            pass
        if place and character is not self.engine.player:
            self._place_in_world(character)
        return self._controllers[character.id]

    def rehydrate(self) -> None:
        """Rebuild the roster after a load: the active player, plus every
        NPC-pool character flagged as a player-character."""
        self._by_id.clear()
        self._controllers.clear()
        self._sync_active()
        for npc in list(self.engine.npc_manager.npcs.values()):
            meta = getattr(npc, "metadata", {}) or {}
            if meta.get("player_char"):
                self._register(npc, PlayerController(
                    meta.get("controller", HUMAN),
                    getattr(npc, "name", "Hero")))

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
        follows (so every system now acts as that hero), and the two
        swap places: the new active leaves the world's NPC pool, the one
        we're leaving joins it as a live entity (M.1b)."""
        self._sync_active()          # register the character we're leaving
        if character.id not in self._by_id and \
                character is not self.engine.player:
            raise KeyError(f"{getattr(character, 'id', '?')} "
                           f"is not in the roster")
        old = self.engine.player
        if character is old:
            return character
        self._take_from_world(character)
        self.engine.player = character
        if old is not None:
            if old.id not in self._controllers:
                self._register(old, PlayerController(
                    name=getattr(old, "name", "Hero")))
            try:
                old.metadata["player_char"] = True
            except Exception:
                pass
            self._place_in_world(old)
        self._sync_active()
        return character

    def humans(self) -> list:
        return [c for c in self.characters
                if self._controllers[c.id].is_human]

    def agents(self) -> list:
        return [c for c in self.characters
                if self._controllers[c.id].is_agent]

    # ---- M.3: absent-player persistence -------------------------

    def set_away(self, character, away: bool = True):
        """Mark a (human) hero as away — an agent keeps it alive until
        the human returns. Remembers where to potter about."""
        ctrl = self.controller_for(character)
        if ctrl is None:
            return None
        ctrl.away = away
        if away and ctrl.away_home is None:
            ctrl.away_home = tuple(getattr(character, "position", (0, 0))
                                   or (0, 0))
        elif not away:
            ctrl.away_home = None
        if away:   # stamp the away-start state for the M.9a return digest
            try:
                from engine.away_digest import snapshot
                snapshot(self.engine, character)
            except Exception:
                pass
        # the `autoplay` setting is the persisted mirror of away-state:
        # keep it honest so the settings overlay never lies (e.g. a
        # keypress that hands control back also clears the toggle)
        try:
            from engine import settings
            settings.set_setting(character, "autoplay",
                                 "on" if away else "off")
        except Exception:
            pass
        return ctrl

    def is_away(self, character) -> bool:
        ctrl = self.controller_for(character)
        return bool(ctrl and ctrl.away)

    def away_characters(self) -> list:
        return [c for c in self.characters if self.is_away(c)]
