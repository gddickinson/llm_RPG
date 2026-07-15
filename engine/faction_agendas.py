"""Faction agendas & diplomacy (P20.3) — wars with aims, not dice.

The faction ticker moved five factions' strength and stores by a nightly
die-roll, but no faction ever WANTED anything: it didn't expand, ally, or
declare war — a die picked the event. This layers intent on top.

Each faction holds an AGENDA (from `data/faction_agendas.json`) it pursues
every night — the brigands expand, the merchants hoard, the guards
protect, the monsters spread — nudging its own strength/stores toward that
aim (which the ticker's raids and the wilderness encounter weight already
read, so an expanding brigand faction really does put more bandits on the
roads). Factions also hold a DIPLOMACY web: sworn enemies drift toward war,
natural friends toward alliance, and crossing a threshold is a `[Realm]`
beat — "the brigands and the guards are at war." And an agenda SHIFTS on
its fortunes: a faction grown strong turns to dominate its rivals; one
beaten low falls back to recover, then resumes its nature.

Heuristic, deterministic; agendas + relations persist.
"""

import logging
import random

logger = logging.getLogger("llm_rpg.faction_agendas")


def _key(a, b):
    return "|".join(sorted((a, b)))


class FactionAgendas:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.agendas: dict = {}
        self.relations: dict = {}
        self.latched: set = set()
        self._ready = False

    def _cfg(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("faction_agendas.json")
        except Exception as e:
            logger.debug(f"faction_agendas.json: {e}")
            return {}

    def _factions(self):
        return list(self.engine.faction_ticker.state.keys())

    def _ensure(self) -> None:
        if self._ready:
            return
        self._ready = True
        cfg = self._cfg()
        if not self.agendas:
            self.agendas = dict(cfg.get("initial", {}))
        facs = self._factions()
        if not self.relations:
            for i, a in enumerate(facs):
                for b in facs[i + 1:]:
                    self.relations[_key(a, b)] = 0
            for a, b in cfg.get("enemies", []):
                self.relations[_key(a, b)] = -30
            for a, b in cfg.get("friends", []):
                self.relations[_key(a, b)] = 30

    # ---- the nightly step ------------------------------------------

    def run_day(self) -> list:
        self._ensure()
        cfg = self._cfg()
        ft = self.engine.faction_ticker
        beats = []
        self._pursue(cfg, ft)
        beats += self._diplomacy(cfg)
        for f in list(self.agendas):
            beat = self._maybe_shift(f, ft, cfg)
            if beat:
                beats.append(beat)
        self._announce(beats)
        return beats

    def _pursue(self, cfg, ft) -> None:
        ag = cfg.get("agendas", {})
        for f, name in self.agendas.items():
            spec = ag.get(name, {})
            st = ft.state.get(f)
            if not st:
                continue
            st["strength"] = min(100, st["strength"] + spec.get("strength", 0))
            st["stores"] = min(100, st["stores"] + spec.get("stores", 0))

    def _diplomacy(self, cfg) -> list:
        enemies = {_key(*p) for p in cfg.get("enemies", [])}
        friends = {_key(*p) for p in cfg.get("friends", [])}
        war_at, ally_at = cfg.get("war_at", -60), cfg.get("ally_at", 60)
        ft = self.engine.faction_ticker
        beats = []
        for key in list(self.relations):
            a, b = key.split("|")
            drift = 0
            heat = (ft.state.get(a, {}).get("strength", 0)
                    + ft.state.get(b, {}).get("strength", 0)) // 40
            if key in enemies:
                drift = -1 - heat        # strong enemies clash harder
            elif key in friends:
                drift = 1
            self.relations[key] = max(-100, min(100, self.relations[key] + drift))
            rel = self.relations[key]
            if rel <= war_at and f"war:{key}" not in self.latched:
                self.latched.add(f"war:{key}")
                self.latched.discard(f"ally:{key}")
                beats.append(f"The {a} and the {b} are at war.")
            elif rel >= ally_at and f"ally:{key}" not in self.latched:
                self.latched.add(f"ally:{key}")
                self.latched.discard(f"war:{key}")
                beats.append(f"The {a} and the {b} have sworn an alliance.")
        return beats

    def _maybe_shift(self, f, ft, cfg):
        st = ft.state.get(f)
        if not st:
            return None
        strength = st["strength"]
        cur = self.agendas.get(f)
        ag = cfg.get("agendas", {})
        strong, weak = cfg.get("strong", 72), cfg.get("weak", 24)
        initial = cfg.get("initial", {}).get(f, cur)
        if strength >= strong and cur in ("expand", "spread") and "dominate" in ag:
            self.agendas[f] = "dominate"
            return f"The {f}, grown strong, move to dominate the region."
        if strength <= weak and cur != "recover" and "recover" in ag:
            self.agendas[f] = "recover"
            return f"The {f}, beaten low, fall back to lick their wounds."
        if cur == "recover" and strength >= (weak + strong) // 2:
            self.agendas[f] = initial
            return f"The {f} have recovered their strength."
        return None

    def _announce(self, beats) -> None:
        for line in beats[:3]:
            self.engine.memory_manager.add_event(f"[Realm] {line}")

    # ---- queries ---------------------------------------------------

    def agenda_of(self, faction: str) -> str:
        self._ensure()
        return self.agendas.get(faction, "")

    def relation(self, a: str, b: str) -> int:
        self._ensure()
        return self.relations.get(_key(a, b), 0)

    def at_war(self, a: str, b: str) -> bool:
        return f"war:{_key(a, b)}" in self.latched

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"agendas": dict(self.agendas),
                "relations": dict(self.relations),
                "latched": sorted(self.latched)}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self.agendas = dict(d.get("agendas", {}))
        self.relations = dict(d.get("relations", {}))
        self.latched = set(d.get("latched", []))
        self._ready = bool(self.agendas)
