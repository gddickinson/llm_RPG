"""Formations I (P17.16) — line & loose, with cohesion.

A formation is a squad property (`squad.formation`), and this module is
what gives P17.5's SET_FORMATION real teeth on the grid. Two archetypes:

  * dense **LINE** — shields overlap, so a man with a standing right-hand
    mate takes +2 to his FRONT-arc defence; depth STEADIES the morale
    (a phalanx doesn't rout at the first push); but it marches at HALF
    pace and takes full missile/AoE damage.

  * **LOOSE / skirmish** — spread out, so it takes HALF from missiles and
    area effects and stays quick, but there is no shield overlap, its
    morale floor is weak, and it is easily flanked.

The glue is COHESION (0–1): the share of the squad that both faces the
body's dominant direction AND stands beside a mate. A tight, unified line
scores high; a scattered or split-facing one scores low. When cohesion
falls past the break point the formation BREAKS — its bonuses vanish and
the shock costs it a step of morale (once). Pure grid geometry, no state
beyond the `formation_broken` latch it sets.
"""

from collections import Counter

from engine.battle import battle_facing as facing

LINE = "line"
LOOSE = "loose"
RING = "ring"            # orbis / schiltron — all-facing (P17.17)
BREAK_COHESION = 0.5

_NEIGH8 = ((1, 0), (-1, 0), (0, 1), (0, -1),
           (1, 1), (1, -1), (-1, 1), (-1, -1))


def _squad_of_id(field, sid):
    return field.squads.get(sid.rsplit("_", 1)[0]) if sid else None


def _has_adjacent_ally(field, soldier) -> bool:
    for dx, dy in _NEIGH8:
        sid = field.soldier_at(soldier.x + dx, soldier.y + dy)
        if sid is None or sid == soldier.sid:
            continue
        sq = _squad_of_id(field, sid)
        if sq is not None and sq.team == soldier.team:
            return True
    return False


def cohesion(field, squad) -> float:
    """0–1: how unified and clustered the squad's ranks are."""
    live = squad.alive_soldiers
    if not live:
        return 0.0
    modal = Counter(tuple(s.facing) for s in live).most_common(1)[0][0]
    formed = sum(1 for s in live
                 if tuple(s.facing) == modal and _has_adjacent_ally(field, s))
    return formed / len(live)


def is_broken(field, squad) -> bool:
    return squad.formation in (LINE, LOOSE) and \
        cohesion(field, squad) < BREAK_COHESION


# ---- effects --------------------------------------------------------

def speed_mult(squad) -> float:
    """A dense LINE and an all-facing RING both crawl; else unslowed."""
    return 0.5 if squad.formation in (LINE, RING) else 1.0


def incoming_ranged_mult(squad) -> float:
    """LOOSE skirmishers take HALF from missiles/AoE; an all-facing RING
    packs tight and outward-facing, so it's MISSILE-VULNERABLE (Falkirk)."""
    if squad.formation == LOOSE:
        return 0.5
    if squad.formation == RING:
        return 1.5
    return 1.0


def all_facing(squad) -> bool:
    return squad.formation == RING


def effective_arc(squad, base_arc: str) -> str:
    """A RING presents its front to EVERY side (P17.17) — the surround-
    counter: no flank or rear bonus lands on an all-facing formation."""
    return "front" if squad is not None and squad.formation == RING \
        else base_arc


def attack_penalty(squad) -> int:
    """A RING fights outward and defensive — its blows land a little
    weaker (offense traded for all-round guard)."""
    return -2 if squad is not None and squad.formation == RING else 0


def _right_mate_stands(field, squad, soldier) -> bool:
    fx, fy = soldier.facing
    sid = field.soldier_at(soldier.x - fy, soldier.y + fx)  # the right hand
    return _squad_of_id(field, sid) is squad


def defense_bonus(field, squad, soldier, attacker) -> int:
    """LINE shield-overlap: +2 to a FRONT-arc defence while the formation
    holds and a right-hand shieldmate still stands. 0 otherwise."""
    if squad.formation != LINE or is_broken(field, squad):
        return 0
    if facing.arc(soldier.facing, attacker.pos, soldier.pos) != "front":
        return 0
    return 2 if _right_mate_stands(field, squad, soldier) else 0


def steady(field, squad) -> int:
    """The morale FLOOR a formation grants each tick: a cohesive LINE
    with depth steadies (+1..+3); loose/broken bodies get nothing."""
    if squad.formation == LINE and not is_broken(field, squad):
        return min(3, len(squad.alive_soldiers) // 4)
    return 0


def check_break(field, squad) -> bool:
    """Latch a formation's break: the first tick cohesion falls past the
    threshold, its bonuses are already gone (via `is_broken`) and it
    takes a one-time morale shock. Returns True on that tick."""
    if squad.formation not in (LINE, LOOSE):
        return False
    broke = cohesion(field, squad) < BREAK_COHESION
    was = squad.formation_broken
    squad.formation_broken = broke
    if broke and not was:
        squad.adjust_morale(-4)
        return True
    return False
