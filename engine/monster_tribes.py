"""Monster tribes as populations (P19.4).

The human factions have a living ticker — strength grows, raids go out,
stores rise and fall. Monsters had none: they were isolated random
spawns. This mirrors the ticker for the wild peoples, so the world holds
hostile SOCIETIES that grow, press on the settlements, and can be beaten
back.

Each tribe (from `data/tribes.json`) carries a `strength` 0-100. Every
night it grows; when it crosses its `raid_threshold` it swarms out of its
terrain to raid the nearest settlement — draining that settlement's
production store, and, if the player is near enough to see it, spilling a
raid party onto the map (raiders tagged with the tribe, so the P19.3 pack
brain coordinates them under a champion). A raid spends `raid_cost` of the
tribe's strength. And every raider the player cuts down beats the tribe
back a little (`on_defeat`) — repel a raid and the tribe is broken below
its threshold for nights to come; ignore it and it grows and returns.

Heuristic, deterministic, no per-tick LLM. Strength persists.
"""

import logging
import random
from typing import Dict, List, Optional

logger = logging.getLogger("llm_rpg.monster_tribes")

STRENGTH_CAP = 100
DEFEAT_HIT = 5           # a slain raider beats the tribe back this much
RAID_DRAIN = 10          # food a successful raid strips from the larder
SEE_RANGE = 22           # a raid this close to the player spills onto the map

# A tribe's AGENDA (George: monsters have goals for their tribes) — a shifting
# collective goal, fortune-driven, that shapes the nightly loop. Mirrors the
# faction agendas (P20.3): a broken tribe digs in, a fed one swarms out.
AGENDA_VERB = {
    "expand": "swells its numbers in the wilds",
    "raid": "sharpens its spears for the raid",
    "fortify": "digs in and mans its totems",
    "plunder": "hungers for a richer hoard",
}


class MonsterTribeSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.strength: Dict[str, int] = {}
        self.agenda: Dict[str, str] = {}      # tid -> current collective goal
        self._loaded = False

    def agenda_of(self, tid: str) -> str:
        """The tribe's current collective goal (expand/raid/fortify/plunder)."""
        return self.agenda.get(tid, "expand")

    def _shift_agenda(self, tid: str, spec: dict) -> Optional[str]:
        """Re-aim the tribe by its fortunes: beaten low it FORTIFIES, war-ready
        it RAIDS, dominant it turns to PLUNDER a richer hoard, else it EXPANDS.
        Returns a `[Realm]` beat when the goal changes."""
        s = self.strength.get(tid, 0)
        thr = spec.get("raid_threshold", 55)
        if s < 25:
            goal = "fortify"
        elif s >= 80:
            goal = "plunder"
        elif s >= thr:
            goal = "raid"
        else:
            goal = "expand"
        if goal != self.agenda.get(tid):
            self.agenda[tid] = goal
            name = self._camp_or_name(tid, spec)
            return f"[Realm] {name} {AGENDA_VERB[goal]}."
        return None

    def _camp_or_name(self, tid: str, spec: dict) -> str:
        tc = getattr(self.engine, "tribe_camps", None)
        camp = tc.camp_name(tid) if tc is not None else None
        return camp or spec.get("name", "A wild tribe")

    # ---- data ------------------------------------------------------

    def _tribes(self) -> Dict[str, dict]:
        from items.data_loader import load_data_file
        try:
            return load_data_file("tribes.json")
        except Exception as e:
            logger.debug(f"tribes.json: {e}")
            return {}

    def _ensure(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        tribes = self._tribes()
        for tid, spec in tribes.items():
            self.strength.setdefault(tid, spec.get("strength", 20))

    def strength_of(self, tid: str) -> int:
        self._ensure()
        return self.strength.get(tid, 0)

    # ---- the nightly step ------------------------------------------

    def run_day(self) -> List[str]:
        self._ensure()
        tribes = self._tribes()
        notes = []
        for tid, spec in tribes.items():
            shift = self._shift_agenda(tid, spec)     # re-aim, then act on it
            if shift:
                notes.append(shift)
            goal = self.agenda_of(tid)
            # the AGENDA shapes the night: EXPAND breeds faster, PLUNDER seizes
            # spoils (a strength surge), RAID swarms out sooner, FORTIFY digs in
            growth = spec.get("growth", 3)
            if goal == "expand":
                growth = int(growth * 1.6) + 1
            self.strength[tid] = min(STRENGTH_CAP,
                                     self.strength.get(tid, 0) + growth)
            if goal == "plunder" and self.rng.random() < 0.5:
                self.strength[tid] = min(STRENGTH_CAP, self.strength[tid] + 8)
                notes.append(f"[Realm] {self._camp_or_name(tid, spec)} "
                             f"plunders the wilds for a richer hoard.")
            thr = spec.get("raid_threshold", 55) - (10 if goal == "raid" else 0)
            if self.strength[tid] >= thr:
                note = self._raid(tid, spec)
                if note:
                    notes.append(note)
        return notes

    def _raid(self, tid: str, spec: dict) -> Optional[str]:
        target = self._target_settlement()
        name = target.name if target is not None else "the outlands"
        drained = self._drain(target)
        self.strength[tid] = max(0, self.strength[tid] - spec.get("raid_cost", 15))
        terrain = spec.get("terrain", "wilds")
        # C3: credit the tribe's CAMP — the raid is its warband marching out
        camp = None
        tc = getattr(self.engine, "tribe_camps", None)
        if tc is not None:
            camp = tc.camp_name(tid)
        line = (f"[Realm] The warband of {camp} swarms out to raid {name}!"
                if camp else
                f"[Realm] {spec['name']} swarm out of the {terrain} to raid {name}!")
        self.engine.memory_manager.add_event(line)
        if drained:
            self.engine.memory_manager.add_event(
                f"[Realm] {name} loses stores to the raiders.")
        self._maybe_spill(tid, spec, target)
        return line

    def _target_settlement(self):
        try:
            setts = self.engine.production._settlements()
        except Exception:
            setts = []
        if not setts:
            return None
        px, py = self.engine.player.position
        return min(setts, key=lambda s: (s.center()[0] - px) ** 2
                   + (s.center()[1] - py) ** 2)

    def _drain(self, target) -> bool:
        if target is None:
            return False
        try:
            store = self.engine.production.store_of(target.name)
        except Exception:
            return False
        goods = [g for g, q in store.items() if q > 0]
        if not goods:
            return False
        good = self.rng.choice(goods)
        store[good] = max(0, store[good] - RAID_DRAIN)
        return True

    def _maybe_spill(self, tid: str, spec: dict, target) -> None:
        """A raid near the player spills raiders onto the map — tagged so
        the P19.3 pack brain runs them under their champion."""
        if target is None:
            return
        px, py = self.engine.player.position
        cx, cy = target.center()
        if abs(cx - px) + abs(cy - py) > SEE_RANGE:
            return                                  # far off — resolved abstractly
        from world.monsters import build_monster
        wmap = self.engine.world.map
        count = 2 + (1 if self.strength[tid] >= spec.get("raid_threshold", 55)
                     + 20 else 0)
        # C3: the raiders ARE the camp's warband — a camp you scouted + thinned
        # sends fewer (a WIPED camp sends none: no warriors left to march)
        tc = getattr(self.engine, "tribe_camps", None)
        if tc is not None and tc.has_camp(tid):
            warriors = tc.living_warriors(tid)
            if warriors <= 0:
                return
            count = min(count, warriors)
        spots = self._free_spots(px, py, count + 1)
        templates = [spec.get("raider", "goblin")] * count
        if self.strength[tid] >= spec.get("raid_threshold", 55) + 20:
            templates.append(spec.get("champion", "bandit"))   # a chieftain rides out
        for tmpl, pos in zip(templates, spots):
            r = build_monster(tmpl, pos)
            r.metadata["tribe"] = tid
            r.metadata["lair"] = f"tribe:{tid}"     # bands via the pack brain
            self.engine.npc_manager.add_npc(r)
            wmap.place_character(r, *pos)

    def _free_spots(self, px, py, n) -> List:
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        out = []
        for r in range(6, 12):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = px + dx, py + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in (TerrainType.BUILDING,
                                              TerrainType.WATER,
                                              TerrainType.MOUNTAIN):
                        continue
                    if wmap.get_character_at(x, y) is not None:
                        continue
                    out.append((x, y))
                    if len(out) >= n:
                        return out
        return out

    # ---- beaten back -----------------------------------------------

    def on_defeat(self, character) -> None:
        """A slain raider beats its tribe back."""
        tid = (getattr(character, "metadata", {}) or {}).get("tribe")
        if not tid or tid not in self.strength:
            return
        was = self.strength[tid]
        # a FORTIFIED tribe is dug in — a slain raider costs it less
        hit = DEFEAT_HIT // 2 if self.agenda_of(tid) == "fortify" else DEFEAT_HIT
        self.strength[tid] = max(0, was - hit)
        spec = self._tribes().get(tid, {})
        thr = spec.get("raid_threshold", 55)
        if was >= thr and self.strength[tid] < thr:
            self.engine.memory_manager.add_event(
                f"[Realm] {spec.get('name', 'The tribe')} are beaten back "
                f"from the raid.")

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"strength": dict(self.strength), "agenda": dict(self.agenda),
                "loaded": self._loaded}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self.strength = {k: int(v) for k, v in d.get("strength", {}).items()}
        self.agenda = {k: str(v) for k, v in d.get("agenda", {}).items()}
        self._loaded = d.get("loaded", bool(self.strength))
