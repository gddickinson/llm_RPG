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


class MonsterTribeSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.strength: Dict[str, int] = {}
        self._loaded = False

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
            self.strength[tid] = min(
                STRENGTH_CAP, self.strength.get(tid, 0) + spec.get("growth", 3))
            if self.strength[tid] >= spec.get("raid_threshold", 55):
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
        line = (f"[Realm] {spec['name']} swarm out of the {terrain} "
                f"to raid {name}!")
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
        self.strength[tid] = max(0, was - DEFEAT_HIT)
        spec = self._tribes().get(tid, {})
        thr = spec.get("raid_threshold", 55)
        if was >= thr and self.strength[tid] < thr:
            self.engine.memory_manager.add_event(
                f"[Realm] {spec.get('name', 'The tribe')} are beaten back "
                f"from the raid.")

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"strength": dict(self.strength), "loaded": self._loaded}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self.strength = {k: int(v) for k, v in d.get("strength", {}).items()}
        self._loaded = d.get("loaded", bool(self.strength))
