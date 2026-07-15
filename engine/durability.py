"""Gear durability — the perpetual material/gold sink (P2.3).

Only top-tier gear degrades (rarity UNCOMMON+ weapons/armor/shields; the
Barrows model: your best-in-slot costs upkeep, commons are worry-free).
Weapons lose durability when you land hits; armor + shields when you take
them. At 0 the item is *broken*: it contributes no damage/armor until
repaired at a forge for a fraction of its value.

State lives in `item.metadata["durability"]` so it serializes for free.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.durability")

WEAPON_MAX = 200      # hits landed before breaking
ARMOR_MAX = 150       # hits absorbed before breaking
REPAIR_COST_FRACTION = 0.15


def is_degradable(item) -> bool:
    if item is None:
        return False
    rarity = getattr(getattr(item, "rarity", None), "value", "common")
    if rarity == "common":
        return False
    return item.is_weapon() or item.is_armor()


def max_durability(item) -> int:
    return WEAPON_MAX if item.is_weapon() else ARMOR_MAX


def get_durability(item) -> Optional[int]:
    """None = this item doesn't degrade."""
    if not is_degradable(item):
        return None
    return item.metadata.setdefault("durability", max_durability(item))


def is_broken(item) -> bool:
    dur = get_durability(item)
    return dur is not None and dur <= 0


def degrade(item, amount: int = 1) -> Optional[str]:
    """Wear the item down; returns a message the turn it breaks."""
    dur = get_durability(item)
    if dur is None or dur <= 0:
        return None
    item.metadata["durability"] = dur - amount
    if item.metadata["durability"] <= 0:
        item.metadata["durability"] = 0
        return f"Your {item.name} breaks! It needs forge repairs."
    return None


def repair_cost(item) -> int:
    dur = get_durability(item)
    if dur is None:
        return 0
    missing = 1.0 - (dur / max_durability(item))
    return max(1, int(item.value * REPAIR_COST_FRACTION * missing)) \
        if missing > 0 else 0


def repair(player, item, at_forge: bool) -> str:
    if not is_degradable(item):
        return f"{item.name} doesn't need repairs."
    if not at_forge:
        return "You need a forge to repair gear."
    cost = repair_cost(item)
    if cost == 0:
        return f"{item.name} is in perfect condition."
    if player.gold < cost:
        return f"Repairs cost {cost}g (you have {player.gold})."
    player.gold -= cost
    item.metadata["durability"] = max_durability(item)
    return f"You repair {item.name} for {cost}g. Good as new."


def durability_label(item) -> str:
    """Short suffix for UI lists, e.g. ' [72%]' or ' [BROKEN]'."""
    dur = get_durability(item)
    if dur is None:
        return ""
    if dur <= 0:
        return " [BROKEN]"
    pct = int(100 * dur / max_durability(item))
    return f" [{pct}%]" if pct < 100 else ""


def damaged_equipped_items(player):
    """Equipped degradable items below full durability."""
    from characters.equipment import equipped_items
    out = []
    for it in equipped_items(player):
        dur = get_durability(it)
        if dur is not None and dur < max_durability(it):
            out.append(it)
    return out
