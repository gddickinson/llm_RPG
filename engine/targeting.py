"""Ranged targeting (P8.7, George's request) — you always know what
you're aiming at.

One target model for missiles AND spells:

- `[` / `]` cycle through valid targets (hostile or provoked, in
  range, with TRUE line of sight from the P8.6 shadowcaster — walls
  and mountains break the lock outdoors, dungeon walls underground).
- The lock is `engine.player_target_id` — the same field companions
  focus-fire on (P7.3), so your party fights what you're aiming at.
- R fires the bow at the lock; offensive spells from the X spellbook
  hit the lock too. A gold reticle marks it on screen; cycling
  announces "Target: Wolf (6 tiles)".
- Stale locks (dead, out of range, sight broken) clear themselves and
  fall back to the nearest valid target.
"""

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.targeting")

MAX_RANGE = 12


def _dist(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class TargetingSystem:
    def __init__(self, engine):
        self.engine = engine

    # -------------------------------------------------------- queries

    def can_hit(self, target) -> Tuple[bool, str]:
        """Range + true line of sight, in whatever space we're in."""
        engine = self.engine
        ppos = engine.player.position
        tpos = target.position
        if _dist(ppos, tpos) > MAX_RANGE:
            return False, f"{target.name} is out of range."
        zone = None
        try:
            zone = engine.active_zone()
        except Exception:
            pass
        try:
            if zone is not None:
                # In a building level, only its own natives are real
                if not hasattr(zone, "rooms") and \
                        target.metadata.get("zone") != \
                        getattr(zone, "name", None):
                    return False, f"{target.name} isn't here."
                from world.fov import zone_fov
                if tuple(tpos) not in zone_fov(zone, tuple(ppos),
                                               radius=MAX_RANGE):
                    return False, (f"No clear shot at {target.name} "
                                   f"— the walls are in the way.")
            else:
                from engine.presence import is_indoors
                if is_indoors(engine, target):
                    return False, f"{target.name} is indoors."
                from world.fov import overworld_los
                if not overworld_los(engine, ppos, tpos,
                                     max_radius=MAX_RANGE):
                    return False, (f"No clear shot at {target.name} "
                                   f"— something solid is in the way.")
        except Exception:
            pass
        return True, ""

    def candidates(self) -> List:
        """Every valid lock, nearest first."""
        engine = self.engine
        out = []
        for npc in engine.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            klass = getattr(npc.character_class, "value", "")
            hostile = klass in ("brigand", "troll", "monster") or \
                npc.metadata.get("provoked") or \
                npc.metadata.get("bounty_hunter")
            if not hostile:
                continue
            ok, _ = self.can_hit(npc)
            if ok:
                out.append(npc)
        out.sort(key=lambda n: _dist(self.engine.player.position,
                                     n.position))
        return out

    def current(self):
        """The locked target if still valid; else nearest; else None."""
        engine = self.engine
        tid = getattr(engine, "player_target_id", None)
        if tid:
            npc = engine.npc_manager.npcs.get(tid)
            if npc is not None and npc.is_active() and \
                    self.can_hit(npc)[0]:
                return npc
        candidates = self.candidates()
        if candidates:
            engine.player_target_id = candidates[0].id
            return candidates[0]
        engine.player_target_id = None
        return None

    # -------------------------------------------------------- actions

    def _announce(self, target) -> str:
        tiles = int(round(_dist(self.engine.player.position,
                                target.position)))
        msg = (f"Target: {target.name} ({tiles} tiles, "
               f"{target.hp}/{target.max_hp} HP). [R] to shoot.")
        self.engine.memory_manager.add_event(msg)
        return msg

    def cycle(self, step: int = 1) -> str:
        candidates = self.candidates()
        if not candidates:
            self.engine.player_target_id = None
            msg = "No targets in sight."
            self.engine.memory_manager.add_event(msg)
            return msg
        tid = getattr(self.engine, "player_target_id", None)
        ids = [n.id for n in candidates]
        idx = (ids.index(tid) + step) % len(ids) if tid in ids else 0
        target = candidates[idx]
        self.engine.player_target_id = target.id
        return self._announce(target)

    def lock_tile(self, x: int, y: int) -> str:
        """Click-to-target: lock whatever stands at (or beside) the
        tile — the most natural way to pick a target (George)."""
        for npc in self.candidates():
            nx, ny = self._display_pos(npc)
            if abs(nx - x) <= 1 and abs(ny - y) <= 1:
                self.engine.player_target_id = npc.id
                return self._announce(npc)
        return "Nothing to target there."

    def _display_pos(self, npc) -> Tuple[int, int]:
        return tuple(npc.position)

    def refresh(self) -> None:
        """Once per turn: keep the lock honest so the reticle shows
        BEFORE you fire. Announces only on acquisition or switch."""
        engine = self.engine
        old = getattr(engine, "player_target_id", None)
        target = self.current()
        if target is not None and target.id != old:
            self._announce(target)
