"""M4 — workers BUILD: settlements physically heal through Worldcraft.

Each night, a settlement with a builder among its folk clears its scars — the
RUBBLE left by a raid/siege becomes open ground again, and SCORCHED earth
regrows — through the same `worldcraft` ruleset the player and spells use (so
non-magical world change obeys the same rules). A town that was sacked slowly
rebuilds itself. Terrain edits persist for FREE (the map snapshot); the system
holds no state of its own, so there's no new save code.
"""

_BUILDER_PROFS = ("carpenter", "mason", "smith")
_BUILDER_CLASSES = ("villager", "merchant", "guard")
_REPAIR = {"rubble": "grass", "scorched": "grass"}   # scars → open ground
MAX_PER_NIGHT = 2
RADIUS = 8


class ConstructionSystem:
    def __init__(self, engine):
        self.engine = engine

    _SKIP = ("stable", "waystone", "chapel", "well", "shrine", "market")

    def _settlements(self):
        # the production loop's settlement list, minus the stable/waystone markers
        # that merely carry a settlement word (so beats read "the folk of Oakvale")
        prod = getattr(self.engine, "production", None)
        base = []
        if prod is not None and hasattr(prod, "_settlements"):
            try:
                base = prod._settlements()
            except Exception:
                base = []
        if not base:
            base = [l for l in self.engine.world.locations
                    if any(w in (getattr(l, "name", "") or "").lower()
                           for w in ("village", "hamlet", "town"))]
        return [l for l in base
                if not any(sk in (getattr(l, "name", "") or "").lower()
                           for sk in self._SKIP)]

    def _has_builder(self, settlement) -> bool:
        cx, cy = settlement.center()
        for npc in self.engine.npc_manager.npcs.values():
            if not (hasattr(npc, "is_alive") and npc.is_alive()):
                continue
            meta = getattr(npc, "metadata", None) or {}
            prof = meta.get("_profession", "")
            cls = getattr(getattr(npc, "character_class", None), "value", "")
            if prof in _BUILDER_PROFS or cls in _BUILDER_CLASSES:
                if abs(npc.position[0] - cx) <= RADIUS and \
                        abs(npc.position[1] - cy) <= RADIUS:
                    return True
        return False

    def _repair_around(self, settlement) -> int:
        from engine import worldcraft
        cx, cy = settlement.center()
        wmap = self.engine.world.map
        done = 0
        for r in range(1, RADIUS + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if done >= MAX_PER_NIGHT:
                        return done
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    to = _REPAIR.get(wmap.get_terrain_at(x, y).value)
                    if not to or (x, y) in wmap.characters:
                        continue
                    ok, _ = worldcraft.mutate(self.engine, x, y, to, "labor",
                                              actor=None, quiet=True)
                    if ok:
                        done += 1
        return done

    def run_day(self):
        """Nightly: each settlement with a builder mends a couple of its scars."""
        beats = []
        for s in self._settlements():
            if not self._has_builder(s):
                continue
            n = self._repair_around(s)
            if n:
                msg = (f"[Realm] The folk of {s.name} clear the ruin and let "
                       f"the land heal ({n} tiles restored).")
                beats.append(msg)
                try:
                    self.engine.memory_manager.add_event(msg)
                except Exception:
                    pass
        return beats
