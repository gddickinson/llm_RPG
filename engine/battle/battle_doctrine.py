"""Doctrine AI (P17.19) — the commander's standing instincts.

Everything the tactics layers built (bracing, formations, hammer-and-
anvil, positional morale) is only as good as the AI that USES it. This
module is the squad-level judgement that runs each tick, turning the
board state into two legible decisions a watching player can read:

  * BRACE WHEN YOU SEE A CHARGE COMING — a spear/pike squad (brace-
    capable) sets to receive the moment an enemy CHARGE unit (cavalry,
    a war-beast) comes within warning range; it stands the hedge down
    again once the horse is gone. This is what makes P17.17's brace
    stance happen without a human hand.

  * COMMIT WHERE YOU ALREADY WIN — a holding RESERVE that isn't itself
    threatened by a charge piles into a nearby fight its side already
    dominates locally (P17.18's reserve commitment), rather than sitting
    idle while a won flank goes unexploited.

Pure, deterministic decisions off the field; `apply` writes the stance
back onto the squad. The rest of the doctrine (deployment templates,
anchoring flanks on terrain, refusing a flank) is P17.19b.
"""

from engine.battle import battle_ai as ai

CHARGE_WARN = 6         # a charger this close and it's time to brace
COMMIT_RANGE = 8        # a reserve commits to a fight within this
ADVANTAGE = 1.5         # ...only where we outnumber locally by this much


def _brace_capable(squad) -> bool:
    return squad.stats.get("bonus_vs_cavalry", 1.0) > 1.0


def incoming_charger(field, squad):
    """The nearest active enemy CHARGE unit bearing down within warning
    range, or None."""
    c = squad.centroid()
    if c is None:
        return None
    best, bd = None, CHARGE_WARN + 1
    for sq in field.squads.values():
        if sq.team == squad.team or not sq.active or sq.charge_bonus <= 1.0:
            continue
        oc = sq.centroid()
        if oc is not None and ai._dist(c, oc) < bd:
            best, bd = sq, ai._dist(c, oc)
    return best


def should_brace(field, squad) -> bool:
    return _brace_capable(squad) and \
        incoming_charger(field, squad) is not None


def local_advantage(field, squad) -> float:
    """Nearby friendly strength ÷ nearby enemy strength (>1 favours us)."""
    c = squad.centroid()
    if c is None:
        return 0.0
    enemy = ai._count_near(field, c, squad.team, foe=True)
    if enemy == 0:
        return 0.0
    return ai._count_near(field, c, squad.team, foe=False) / enemy


def _nearest_enemy_dist(field, squad):
    c = squad.centroid()
    if c is None:
        return None
    best = None
    for sq in field.squads.values():
        if sq.team == squad.team or not sq.active:
            continue
        oc = sq.centroid()
        if oc is not None:
            d = ai._dist(c, oc)
            best = d if best is None else min(best, d)
    return best


def should_commit(field, squad) -> bool:
    """A holding reserve piles on where the side already wins locally —
    but not if it's itself the anchor a charge is bearing down on."""
    if squad.order != "hold":
        return False
    if _brace_capable(squad) and incoming_charger(field, squad) is not None:
        return False
    # already trading blows? it IS committed — let it fight, don't re-order
    if any(ai.adjacent_enemies(field, s) > 0 for s in squad.alive_soldiers):
        return False
    d = _nearest_enemy_dist(field, squad)
    if d is None or d > COMMIT_RANGE:
        return False                      # no nearby fight to pile into
    return local_advantage(field, squad) >= ADVANTAGE


def apply(field, squad) -> None:
    """Write the doctrine's stance onto an active squad each tick."""
    if not squad.active:
        return
    squad.braced = should_brace(field, squad)
    if should_commit(field, squad):
        squad.order = "charge"
