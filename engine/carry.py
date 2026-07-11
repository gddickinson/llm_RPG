"""Carry capacity (George: "a character shouldn't be able to carry an
infinite amount of items").

Slot-based: a stack occupies one slot, capacity grows with Strength
(18 + 2 per STR modifier — a STR 14 adventurer hauls 22 stacks, a
STR 6 scholar 14). Enforced at the acquisition points a player
actually hits: pickup, foraging, gathering, harvest, shop purchases,
rummaging and structure chests (which stay lootable until you make
room). Quest rewards and gifts are never blocked — refusing a reward
is worse than a heavy pack. A full weight model (per-item weights,
encumbrance slowdown) can layer on later; slots first because they're
legible at a glance.
"""

BASE_SLOTS = 18


def capacity(player) -> int:
    mod = (getattr(player, "strength", 10) - 10) // 2
    return max(8, BASE_SLOTS + 2 * mod)


def used_slots(player) -> int:
    return len(getattr(player, "inventory", []))


def can_carry(player, extra: int = 1) -> bool:
    return used_slots(player) + extra <= capacity(player)


def full_message(player) -> str:
    return (f"Your pack is full ({used_slots(player)}/"
            f"{capacity(player)}). Drop, sell or bank something.")
