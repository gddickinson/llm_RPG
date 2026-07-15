"""P31.1c — the tower guards defend.

A guard stationed at a corner wall tower (P31.1b, flagged `tower_guard`) keeps
watch from its ROOF: it SPOTS an approaching hostile from its height, cries the
ALARM to the town the first time, and looses ARROWS down at the attacker —
ranged, from beyond a walker's reach and over the wall. Run each turn from the
pipeline beside the P7.1 npc_conflict. Transient; the guards ride the NPC save.
"""

import logging

logger = logging.getLogger("llm_rpg.tower_defense")

TOWER_RANGE = 8            # a rooftop guard sees & shoots far (height)
ARROW_DAMAGE = 6
ARROW_DC = 8              # a rooftop archer rarely misses a target below
EARSHOT = 12             # only log a tower's alarm/arrows near the player
_HOSTILE = ("brigand", "monster", "troll")


class TowerDefense:
    def __init__(self, engine):
        self.engine = engine

    def _tower_guards(self):
        return [n for n in self.engine.npc_manager.npcs.values()
                if n.is_active() and (getattr(n, "metadata", {}) or {})
                .get("tower_guard")]

    def _nearest_hostile(self, pos):
        best, bd = None, TOWER_RANGE + 1
        for n in self.engine.npc_manager.npcs.values():
            if not n.is_active():
                continue
            if getattr(getattr(n, "character_class", None), "value", "") \
                    not in _HOSTILE:
                continue
            px, py = getattr(n, "position", (None, None))
            if px is None:
                continue
            d = max(abs(px - pos[0]), abs(py - pos[1]))
            if d < bd:
                best, bd = n, d
        return best

    def update(self) -> int:
        """Each manned tower shoots at the nearest hostile in range. Returns
        the number of arrows loosed this turn."""
        shots = 0
        for guard in self._tower_guards():
            target = self._nearest_hostile(guard.position)
            if target is None:
                guard.metadata.pop("alarmed", None)   # all clear
                continue
            if not guard.metadata.get("alarmed"):
                guard.metadata["alarmed"] = True
                self._announce(
                    "[Alarm] A tower guard cries out — raiders at the walls!",
                    guard.position)
            self._shoot(guard, target)
            shots += 1
        return shots

    def _shoot(self, guard, target) -> None:
        rng = getattr(getattr(self.engine, "combat_system", None), "rng", None)
        roll = rng.randint(1, 20) if rng is not None else 14
        if roll >= ARROW_DC:
            try:
                target.take_damage(ARROW_DAMAGE)
            except Exception:
                return
            self._announce(
                f"[Guard] An arrow from the tower thuds into {target.name}!",
                guard.position)
            if not target.is_active():
                self._announce(
                    f"[Guard] {target.name} falls beneath the wall.",
                    guard.position)
        else:
            self._announce(
                f"[Guard] An arrow from the tower whistles past {target.name}.",
                guard.position)

    def _near_player(self, pos) -> bool:
        try:
            p = self.engine.player.position
            return max(abs(p[0] - pos[0]), abs(p[1] - pos[1])) <= EARSHOT
        except Exception:
            return True

    def _announce(self, text, pos=None) -> None:
        # a tower's cry/arrows only reach the LOG when the player is near — a
        # skirmish across the map is silent (keeps the log readable, like the
        # P7.1 [Clash] earshot rule)
        if pos is not None and not self._near_player(pos):
            return
        try:
            self.engine.memory_manager.add_event(text)
        except Exception:
            pass
