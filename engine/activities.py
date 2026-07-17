"""LIVING_WORLD A1 — the per-turn ACTIVITY system.

The audit finding: a scheduled NPC that reaches its work location just LOITERS —
a smith "at work" looks identical to an idle villager, because `schedules.
activity_to_action` flattened work/pray/play to a bare "move". This layer makes a
nearby NPC *perform* the activity it already has in its schedule: it plays a
fitting animation (a smith HAMMERS, a cleric KNEELS in prayer, a bard DANCES a
tune), sets an expression, and now and then drops a `[Town]` beat.

Cheap by design — it only ever touches the handful of NPCs already ticked near
the player (`game_engine._npc_turns_due` gate), reuses the existing clip library
(`ui/char_clips`) via the pygame-free `engine/anim` triggers, and reads the
existing profession/building data (`world/building_types`). Content is data
(`data/activities.json`); no per-tick LLM. `action_router._handle_move` calls
`perform` when a scheduled worker has arrived; a non-work activity falls back to
the loiter stroll, so nothing regresses.
"""

import json
import logging
import math
import os
import random

logger = logging.getLogger("llm_rpg.activities")

# activities that PERFORM in place at the work location (vs stroll/patrol/wander)
PERFORM = frozenset({"work", "pray", "play", "eat", "drink"})

BEAT_WITNESS_DIST = 5      # only beat about a worker the player is near enough to see
BEAT_CHANCE = 0.4         # ... and then only sometimes, so the log stays sparse

PATROL_RADIUS = 5         # A2: a guard's beat ring when no gates to walk
PATROL_POINTS = 8

WORKSITE_SPREAD = 2       # A3: workers fan out to a personal tile ±this at the workplace
COMMUTE_MAX = 6           # ... but settle & work where they are if it's unreachable
WORK_YIELD_PERIOD = 16    # A4: a gatherer adds 1 raw to the store every N performs
CROWD_DIST = 3            # A3: a bard's audience turns to watch within this range


class ActivitySystem:
    def __init__(self, engine):
        self.engine = engine
        self._data = _load()
        self.activities = self._data.get("activities", {})
        self.professions = self._data.get("professions", {})
        self.class_work = self._data.get("class_work", {})

    # ------------------------------------------------------------- query
    def is_perform(self, activity: str) -> bool:
        return activity in PERFORM

    def profession_of(self, npc):
        """The producer profession an NPC works — from its WORKPLACE building's
        kind (`home_location` → `Location.kind` → `building_types`). Cached on
        metadata (incl. a '' sentinel for 'resolved, none')."""
        meta = getattr(npc, "metadata", None)
        if meta is None:
            return None
        if "_profession" in meta:
            return meta["_profession"] or None
        prof = self._resolve_profession(npc)
        meta["_profession"] = prof or ""
        return prof

    def _resolve_profession(self, npc):
        name = getattr(npc, "home_location", "") or ""
        if not name:
            return None
        from world.building_types import profession_of_kind
        for loc in self.engine.world.locations:
            if loc.name == name:
                kind = loc.get_property("kind") or loc.get_property("type") or ""
                return profession_of_kind(kind)
        return None

    def spec_for(self, npc, activity: str):
        """Resolve an NPC's activity to a {clip, expr, beat, period} spec: a
        'work' activity is refined by the NPC's profession (its building), else
        its class, else the generic work clip."""
        base = self.activities.get(activity)
        if base is None:
            return None
        spec = dict(base)
        if activity == "work":
            prof = self.profession_of(npc)
            if prof and prof in self.professions:
                spec.update(self.professions[prof])
            else:
                klass = getattr(getattr(npc, "character_class", None), "value", "")
                if klass in self.class_work:
                    spec.update(self.class_work[klass])
        return spec

    # ------------------------------------------------------------- act
    def perform(self, npc, activity: str, center=None) -> bool:
        """Play the activity's animation + expression on `npc` and occasionally
        emit a beat. Returns True when it handled the turn (so the caller doesn't
        loiter). A3: for WORK the NPC first walks to a personal WORKSITE tile at
        the workplace (so a crowd of workers fans out instead of stacking on one
        spot); A4: a gatherer's work feeds its raw into the settlement store."""
        spec = self.spec_for(npc, activity)
        if not spec:
            return False
        if activity == "work" and center is not None and \
                self._goto_worksite(npc, center):
            return True                       # still commuting to its spot
        try:
            from engine import anim
            anim.emote(npc, spec.get("clip", "stoop"))
            if spec.get("expr"):
                anim.express(npc, spec["expr"])
        except Exception as e:
            logger.debug(f"activity anim failed: {e}")
        if activity == "work":
            self._work_yield(npc)             # A4: gatherers stock the larder
        elif activity == "play":
            self._draw_crowd(npc)             # A3: a bard gathers an audience
        self._maybe_beat(npc, spec)
        return True

    # ------------------------------------------------------------- worksite (A3)
    def _goto_worksite(self, npc, center) -> bool:
        """Walk to a stable per-person tile near the workplace centre; True while
        still commuting (so a crowd of workers spreads out, not stacks). If the
        ideal tile can't be reached within COMMUTE_MAX steps (a wall in the way),
        the worker SETTLES where it is and works — never stuck sliding forever."""
        meta = getattr(npc, "metadata", None)
        if meta is None:
            return False
        ws = meta.get("_worksite")
        if ws is None or meta.get("_worksite_center") != list(center):
            ws = self._worksite_for(npc, center)
            meta["_worksite"] = ws
            meta["_worksite_center"] = list(center)
            meta["_commute"] = 0
        pos = npc.position
        if abs(pos[0] - ws[0]) + abs(pos[1] - ws[1]) <= 1:
            return False                      # arrived (or adjacent) → work here
        if meta.get("_commute", 0) >= COMMUTE_MAX:     # can't reach it → settle
            meta["_worksite"] = tuple(pos)
            return False
        meta["_commute"] = meta.get("_commute", 0) + 1
        from engine.squad_tactics import greedy_step
        before = tuple(pos)
        greedy_step(self.engine.world.map, npc, tuple(ws))
        return tuple(npc.position) != before  # moved → still commuting

    @staticmethod
    def _worksite_for(npc, center):
        h = 0
        for ch in (getattr(npc, "id", "") or "x"):
            h = (h * 131 + ord(ch)) & 0x7fffffff
        span = 2 * WORKSITE_SPREAD + 1
        dx = (h % span) - WORKSITE_SPREAD
        dy = ((h // span) % span) - WORKSITE_SPREAD
        return (center[0] + dx, center[1] + dy)

    # ------------------------------------------------------------- economy (A4)
    def _work_yield(self, npc) -> None:
        """A gatherer's visible work stocks the settlement larder with its raw
        (so watching a miner adds ore — crafters stay cosmetic, the nightly
        production loop turns the raws into goods). Rate-limited + capped."""
        prof = self.profession_of(npc)
        if not prof:
            return
        from engine import production as pr
        raw = pr.primary_raw(prof)            # None for crafters (smith/cook/…)
        if not raw:
            return
        meta = getattr(npc, "metadata", None)
        if meta is None:
            return
        n = meta.get("_yield_ticks", 0) + 1
        meta["_yield_ticks"] = n
        if n % WORK_YIELD_PERIOD != 0:
            return
        prod = getattr(self.engine, "production", None)
        if prod is None:
            return
        try:
            setts = prod._settlements()
            s = prod._nearest(setts, npc.position) if setts else None
            if s is None:
                return
            from engine.production_loop import STORE_CAP
            store = prod.store_of(s.name)
            store[raw] = min(STORE_CAP, store.get(raw, 0) + 1)
        except Exception as e:
            logger.debug(f"work yield failed: {e}")

    # ------------------------------------------------------------- crowd (A3)
    def _draw_crowd(self, npc) -> None:
        """Nearby idle folk turn to watch a performing bard (cosmetic — they keep
        their own behaviour, they just face the show)."""
        try:
            from engine import anim
            x, y = npc.position
            for other in self.engine.npc_manager.npcs.values():
                if other.id == npc.id or not other.is_active():
                    continue
                ox, oy = other.position
                if abs(ox - x) + abs(oy - y) <= CROWD_DIST:
                    anim.face(other, (x, y))
        except Exception as e:
            logger.debug(f"draw crowd failed: {e}")

    # ------------------------------------------------------------- patrol (A2)
    def patrol_step(self, npc, center) -> bool:
        """A2: a guard on patrol walks a fixed BEAT — the settlement's gates when
        it has them (a guard checks the gates), else a ring around the centre —
        stepping waypoint to waypoint instead of loitering. State on metadata."""
        meta = getattr(npc, "metadata", None)
        if meta is None:
            return False
        route = meta.get("_patrol_route")
        if not route or meta.get("_patrol_center") != list(center):
            route = self._patrol_waypoints(center)
            meta["_patrol_route"] = route
            meta["_patrol_center"] = list(center)
            meta["_patrol_i"] = 0
            meta["_patrol_stuck"] = 0
        if not route:
            return False
        i = meta.get("_patrol_i", 0) % len(route)
        pos = tuple(npc.position)
        tgt = tuple(route[i])
        if abs(pos[0] - tgt[0]) + abs(pos[1] - tgt[1]) <= 1:   # reached → next
            i = (i + 1) % len(route)
            meta["_patrol_i"] = i
            meta["_patrol_stuck"] = 0
            tgt = tuple(route[i])
        # a real BFS path step — routes AROUND buildings to reach a distant gate
        from engine.squad_tactics import path_step
        path_step(self.engine.world.map, npc, tgt)
        if tuple(npc.position) != pos:               # made progress on the beat
            meta["_patrol_stuck"] = 0
            return True
        stuck = meta.get("_patrol_stuck", 0) + 1     # blocked → skip this waypoint
        meta["_patrol_stuck"] = stuck
        if stuck >= 4:
            meta["_patrol_i"] = (i + 1) % len(route)
            meta["_patrol_stuck"] = 0
        return False

    def _patrol_waypoints(self, center):
        """The gate tiles of the nearest walled settlement (a guard walks the
        gates), else a ring of points around the centre."""
        best, bd = None, 1e18
        for loc in self.engine.world.locations:
            gates = loc.get_property("gates")
            if gates and len(gates) >= 2:
                c = loc.center()
                d = (c[0] - center[0]) ** 2 + (c[1] - center[1]) ** 2
                if d < bd:
                    bd, best = d, gates
        if best and bd <= (PATROL_RADIUS * 4) ** 2:
            return [tuple(g) for g in best]
        return [(int(center[0] + PATROL_RADIUS * math.cos(2 * math.pi * k / PATROL_POINTS)),
                 int(center[1] + PATROL_RADIUS * math.sin(2 * math.pi * k / PATROL_POINTS)))
                for k in range(PATROL_POINTS)]

    def _maybe_beat(self, npc, spec) -> None:
        beat = spec.get("beat")
        if not beat:
            return
        meta = getattr(npc, "metadata", None)
        if meta is None:
            return
        ticks = meta.get("_activity_ticks", 0) + 1
        meta["_activity_ticks"] = ticks
        if ticks % max(1, spec.get("period", 10)) != 0:
            return
        player = getattr(self.engine, "player", None)
        if player is None:
            return
        px, py = player.position
        nx, ny = npc.position
        if abs(px - nx) + abs(py - ny) > BEAT_WITNESS_DIST:
            return
        if random.random() < BEAT_CHANCE:
            self.engine.memory_manager.add_event(f"[Town] {npc.name} {beat}.")


def _load():
    try:
        with open(os.path.join("data", "activities.json")) as fp:
            return json.load(fp)
    except Exception as e:
        logger.warning(f"activities.json missing/broken: {e}")
        return {"activities": {}, "professions": {}, "class_work": {}}
