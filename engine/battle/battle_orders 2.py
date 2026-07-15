"""Battle orders (P17.5) — the commander's verbs, as behaviour.

A squad already carried an `order` string, but only "focus" changed
anything; "hold" and "charge" advanced identically. This module
gives the verbs real meaning on the grid and is the single place the
session asks "given this squad's order, what does a soldier out of
reach want to do?".

Verbs (what the command UI issues to an allied squad):
  CHARGE / FOCUS_FIRE  → advance into the enemy (focus_fire also
                         concentrates target selection on one squad)
  HOLD                 → root in place; fight only what comes to you
  FALL_BACK            → withdraw away from the nearest enemy
  MOVE                 → march to an ordered tile, ignoring the enemy
  SET_FORMATION        → change formation (layout/defence; grid
                         effects land with P17.10)

Objectives (a squad's win-goal beyond "kill everyone") are scaffolded
here; capture-point VICTORY wiring belongs with P17.6's siege.
Everything is pure and deterministic — no pygame, no rng.
"""

# ---- order verbs -------------------------------------------------
CHARGE = "charge"
HOLD = "hold"
FALL_BACK = "fallback"
MOVE = "move"
FOCUS_FIRE = "focus_fire"
SET_FORMATION = "formation"

# "focus" is the legacy spelling kept working for old saves/scenarios
_FOCUS_ALIASES = frozenset({"focus", FOCUS_FIRE})

# the set a commander can cycle a squad through (formation is its own
# UI action; objectives are set by the scenario, not toggled in play)
ORDERS = (CHARGE, HOLD, FOCUS_FIRE, FALL_BACK, MOVE)

# how each order reads to the player (command overlay labels)
ORDER_LABEL = {
    CHARGE: "Charge", HOLD: "Hold", FOCUS_FIRE: "Focus Fire",
    FALL_BACK: "Fall Back", MOVE: "Move", SET_FORMATION: "Formation",
}

# ---- objectives (scaffold; victory wiring is P17.6) --------------
CAPTURE_POINT = "capture_point"
BREACH = "breach"
PROTECT = "protect"
OBJECTIVES = (CAPTURE_POINT, BREACH, PROTECT)


def is_focus(order) -> bool:
    """True when the order concentrates fire on the ordered squad."""
    return order in _FOCUS_ALIASES


def advance_intent(squad) -> str:
    """What a soldier of this squad wants when NO enemy is in reach.
    One of: 'advance' (close on the foe), 'hold' (stay put),
    'retreat' (withdraw), 'goto' (march to the ordered tile)."""
    o = squad.order
    if o == HOLD:
        return "hold"
    if o == FALL_BACK:
        return "retreat"
    if o == MOVE and _is_tile(squad.order_target):
        return "goto"
    return "advance"            # charge, focus_fire, or default


def _is_tile(target) -> bool:
    return (isinstance(target, (tuple, list)) and len(target) == 2
            and all(isinstance(v, int) for v in target))


def valid_order(order) -> bool:
    return order in ORDERS or order in _FOCUS_ALIASES \
        or order == SET_FORMATION
