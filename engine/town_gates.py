"""P31.1d — town gates that close and lock.

The wall gates (P31.1b, stored on the Oakvale location's `gates`) are no longer
always-open holes: they CLOSE at night and under an ALARM (a tower guard has
spotted raiders), and a closed gate turns back what the guards can't. A closed
gate is modelled as its tile reverting to WALL (BUILDING) so the existing
movement wall-guard stops everyone; opening restores the ROAD. Forcing a shut
gate is loud and a crime.

State (per gate: open / closed / locked) persists. `sync` runs each turn from
the pipeline: open by day, close at night, LOCK down while the alarm sounds.
"""

import logging

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.town_gates")

WALL = TerrainType.BUILDING
ROAD = TerrainType.ROAD


class TownGateSystem:
    def __init__(self, engine, seed=None):
        self.engine = engine
        self.state = {}          # "x,y" -> "open" | "closed" | "locked"

    # ---- the gates -------------------------------------------------

    def _gates(self):
        oak = next((l for l in self.engine.world.locations
                    if l.name == "Oakvale Village"), None)
        if oak is None:
            return []
        return [tuple(g) for g in (oak.get_property("gates") or [])]

    def _key(self, gate):
        return f"{gate[0]},{gate[1]}"

    def state_of(self, gate) -> str:
        return self.state.get(self._key(gate), "open")

    def is_open(self, gate) -> bool:
        return self.state_of(gate) == "open"

    def is_locked(self, gate) -> bool:
        return self.state_of(gate) == "locked"

    def gate_at(self, pos):
        """The gate at `pos`, or None — a fast tile lookup for movement/hints."""
        for g in self._gates():
            if g == (pos[0], pos[1]):
                return g
        return None

    def closed_gate_near(self, pos, r: int = 1):
        """The nearest shut (closed/locked) gate within `r` — for the hint bar."""
        for g in self._gates():
            if abs(g[0] - pos[0]) <= r and abs(g[1] - pos[1]) <= r \
                    and not self.is_open(g):
                return g
        return None

    # ---- the player walks THROUGH a shut gate ----------------------

    def player_step_open(self, pos):
        """The player steps into a shut town gate. An unlocked one swings OPEN
        for them (they live here / are a traveller — no crime); a LOCKED gate
        (raiders at the walls) stays barred. Returns a line if it opened, so the
        move can proceed onto the now-ROAD tile, else None."""
        g = self.gate_at(pos)
        if g is None or self.is_open(g):
            return None
        if self.is_locked(g):
            return None                      # barred by the alarm — force it
        if self._set_tile(g, closed=False):
            self.state[self._key(g)] = "open"
            return "The town gate swings open for you."
        return None

    # ---- open / close ----------------------------------------------

    def _set_tile(self, gate, closed: bool) -> bool:
        wmap = self.engine.world.map
        gx, gy = gate
        if not (0 <= gx < wmap.width and 0 <= gy < wmap.height):
            return False
        if (gx, gy) in wmap.characters:      # never shut a gate on someone
            return False
        if closed and wmap.terrain[gy][gx] == ROAD:
            wmap.terrain[gy][gx] = WALL
        elif not closed and wmap.terrain[gy][gx] == WALL:
            wmap.terrain[gy][gx] = ROAD
        return True

    def open_all(self) -> int:
        opened = 0
        for g in self._gates():
            if self._set_tile(g, closed=False):
                self.state[self._key(g)] = "open"
                opened += 1
        return opened

    def close_all(self, locked: bool = False) -> int:
        closed = 0
        for g in self._gates():
            if self._set_tile(g, closed=True):
                self.state[self._key(g)] = "locked" if locked else "closed"
                closed += 1
        return closed

    # ---- the player forces a shut gate (a noisy crime) -------------

    def force_gate(self, gate) -> str:
        if self.is_open(gate):
            return "The gate stands open."
        if self._set_tile(gate, closed=False):
            self.state[self._key(gate)] = "open"
            try:
                self.engine.memory_manager.add_event(
                    "[Law] You force the town gate — it bangs open, and "
                    "heads turn. That won't be forgotten.")
            except Exception:
                pass
            return "You force the gate open."
        return "Something blocks the gate."

    # ---- the clock & the alarm drive the gates ---------------------

    def _alarm_ringing(self) -> bool:
        return any((getattr(n, "metadata", {}) or {}).get("alarmed")
                   for n in self.engine.npc_manager.npcs.values())

    def _is_night(self) -> bool:
        try:
            return self.engine.world.get_time_of_day() in ("night", "evening")
        except Exception:
            return False

    def sync(self) -> None:
        """Run each turn: LOCK the gates while raiders are at the walls, else
        CLOSE them by night and OPEN them by day."""
        if not self._gates():
            return
        if self._alarm_ringing():
            self.close_all(locked=True)
        elif self._is_night():
            self.close_all(locked=False)
        else:
            self.open_all()

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"state": dict(self.state)}

    def from_dict(self, d: dict) -> None:
        self.state = dict((d or {}).get("state", {}))
