"""P32.1 pursuit speed — a faster creature runs the hero down.

The overworld advances one tile per turn and the ambient NPC AI only stirs
every ``config.NPC_ACTION_INTERVAL`` turns, so a fleeing hero used to outrun
anything just by walking — a monster stepped toward the player once every five
strides the player took. This governor runs EVERY real turn (from the turn
pipeline, NOT gated by that throttle) and moves each nearby HOSTILE pursuer
toward the player at its own ``speed`` (tiles/turn), banked in a fractional
accumulator — the same ``move_accum`` trick the P17 battle layer uses:

* a wolf (1.5) banks half a stride a turn and closes the gap,
* a shambling skeleton (0.6) falls behind and is left in the dust,
* a plain foe (1.0) keeps pace but can never gain.

A mounted hero on a road still escapes the pack: road-pace strides don't tick
the turn, so the pursuit clock doesn't run for them. This is MOVEMENT only —
pursuit closes to a STANDOFF (``HOLD_DIST`` tiles) and stops there; the final
adjacent step and the bite are the ambient AI's job. So a pursuer keeps pace on
your heels but never parks on the very tile you're about to step onto.
"""

HOSTILE_CLASSES = ("brigand", "monster", "troll")
CHASE_RADIUS = 12        # a hostile within this many tiles gives chase
MAX_STEPS = 3            # a very fast creature blurs, it never teleports
HOLD_DIST = 1            # P37.6b: pursuit closes to ADJACENT (was a 2-tile
#                          standoff) so a hostile actually reaches melee — the
#                          bite is the AggressionSystem's, EVERY turn. It parks
#                          adjacent (never on your tile), keeping pace so a
#                          so you can't simply walk away from a faster creature.


def creature_speed(char) -> float:
    """A character's overworld pace in tiles/turn (default 1.0, always > 0)."""
    md = getattr(char, "metadata", {}) or {}
    try:
        s = float(md.get("speed", 1.0))
    except (TypeError, ValueError):
        return 1.0
    return s if s > 0 else 1.0


def _cls(npc) -> str:
    return getattr(getattr(npc, "character_class", None), "value", "")


def _cheb(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class PursuitSystem:
    """Advance nearby hostile pursuers toward the player each turn by speed."""

    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------ tick

    def update(self) -> int:
        """Move every nearby hostile pursuer by its speed. Returns the number
        of extra pursuit steps taken this turn (0 if nothing chased)."""
        engine = self.engine
        player = getattr(engine, "player", None)
        if player is None or getattr(player, "hp", 1) <= 0:
            return 0
        ppos = tuple(player.position)
        wmap = engine.world.map
        try:
            party = set(engine.companion_manager.party)
        except Exception:
            party = set()
        steps = 0
        for npc in list(engine.npc_manager.npcs.values()):
            if not self._is_pursuer(npc, party, wmap):
                continue
            if _cheb(npc.position, ppos) > CHASE_RADIUS:
                npc.metadata["chase_accum"] = 0.0      # out of the chase
                continue
            steps += self._advance(npc, ppos, wmap)
        return steps

    # ------------------------------------------------------- eligibility

    def _is_pursuer(self, npc, party, wmap) -> bool:
        try:
            if not npc.is_active():
                return False
        except Exception:
            pass
        if getattr(npc, "hp", 0) <= 0:
            return False
        if npc.id in party:
            return False
        meta = getattr(npc, "metadata", {}) or {}
        if meta.get("player_char") or meta.get("adventurer"):
            return False
        # freshly shoved this turn — staggered, doesn't step back at you (a
        # one-turn skip so a knockback isn't instantly undone by pursuit)
        if meta.pop("shoved", None):
            return False
        if _cls(npc) not in HOSTILE_CLASSES:
            return False
        # only creatures actually on the overworld grid — a zone NPC (an
        # interior / tutorial island) lives in a different coordinate space
        # and must never chase across grids
        try:
            if wmap.get_character_at(*npc.position) is not npc:
                return False
        except Exception:
            return False
        # a broken or badly-hurt creature is running, not chasing
        if meta.get("pack_broken"):
            return False
        beh = meta.get("behavior", {}) or {}
        flee_below = beh.get("flee_below", 0)
        if flee_below and npc.hp / max(1, npc.max_hp) <= flee_below:
            return False
        return True

    # ---------------------------------------------------------- movement

    def _advance(self, npc, ppos, wmap) -> int:
        meta = npc.metadata
        accum = float(meta.get("chase_accum", 0.0)) + creature_speed(npc)
        taken = 0
        while accum >= 1.0 and taken < MAX_STEPS:
            if _cheb(npc.position, ppos) <= HOLD_DIST:
                break                       # standoff — the ambient AI closes
            if not self._step_toward(npc, ppos, wmap):
                break                       # blocked by wall / occupancy
            accum -= 1.0
            taken += 1
        meta["chase_accum"] = accum
        return taken

    def _step_toward(self, npc, target, wmap) -> bool:
        x, y = npc.position
        dx = (target[0] > x) - (target[0] < x)
        dy = (target[1] > y) - (target[1] < y)
        horiz_first = abs(target[0] - x) >= abs(target[1] - y)
        cands = []
        if dx and dy:
            cands.append((dx, dy))                       # prefer the diagonal
        cands.append((dx, 0) if horiz_first else (0, dy))
        cands.append((0, dy) if horiz_first else (dx, 0))
        for mx, my in cands:
            if mx == 0 and my == 0:
                continue
            nx, ny = x + mx, y + my
            if (nx, ny) == tuple(target):
                continue                    # never step onto the player
            if wmap.move_character(npc, nx, ny):
                return True
        return False
