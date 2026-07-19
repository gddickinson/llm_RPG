"""Trade info (PUX.2) — the numbers behind a merchant's deal.

Pure helpers the shop panel renders so a player can SEE what an item
does, how it stacks up against what they're wearing, and WHY a price
is what it is (the faction / shortage / market / stock / region
multipliers that were always applied but never shown) — plus the
maths for buying and selling in bulk. No pygame here; the panel draws
what these return, so the logic is unit-tested directly.
"""

from typing import List, Optional, Tuple

from characters.equipment import get_equipment, slot_for_item
from items.item import ItemRarity, ItemType

BULK = 5                 # units a Shift+Enter buys/sells at once
JUNK_MAX_VALUE = 25      # a common misc trinket at or under this is "junk"


def _signed(n) -> str:
    return f"+{n}" if n >= 0 else str(n)


def item_report(item) -> List[str]:
    """A few lines describing what the item IS — for the inspect pane."""
    lines = [f"{item.name} — {item.rarity.value} {item.item_type.value}"]
    if item.is_weapon():
        two = "  two-handed" if getattr(item, "two_handed", False) else ""
        lines.append(f"Damage {item.damage} ({item.damage_kind}){two}")
    if item.is_armor():
        lines.append(f"Armour {item.armor}")
    bonuses = getattr(item, "equip_bonuses", {}) or {}
    if bonuses:
        lines.append("  ".join(f"{_signed(v)} {k}"
                               for k, v in bonuses.items()))
    use = getattr(item, "use_effect", {}) or {}
    if use.get("spell"):
        lines.append(f"Casts {use['spell']}")
    elif use.get("effect"):
        lines.append(f"Grants {use['effect']}")
    elif use.get("heal"):
        lines.append(f"Heals {use['heal']}")
    tail = f"Value {item.value}g"
    if getattr(item, "weight", 0):
        tail = f"Weight {item.weight}   " + tail
    lines.append(tail)
    return lines


def compare_to_equipped(engine, item) -> Optional[str]:
    """How the item measures up against what's worn in its slot, or
    None if it isn't equippable."""
    slot = slot_for_item(item)
    if slot is None:
        return None
    worn = get_equipment(engine.player).get(slot.value)
    if worn is None:
        return f"equips to {slot.value} (empty)"
    if worn is item:
        return "currently equipped"
    if item.is_weapon():
        return f"{_signed(item.damage - worn.damage)} dmg vs your {worn.name}"
    if item.is_armor():
        return f"{_signed(item.armor - worn.armor)} armour vs your " \
               f"{worn.name}"
    return f"would replace {worn.name}"


def price_factors(sm, player, item, merchant,
                  selling: bool) -> List[Tuple[str, float]]:
    """The multipliers that moved this price off the item's base value
    — only the ones that actually deviate, so the line stays short."""
    eng = sm.engine
    out: List[Tuple[str, float]] = []

    def add(label, fn):
        try:
            m = float(fn())
            if abs(m - 1.0) > 0.005:
                out.append((label, m))
        except Exception:
            pass

    add("reputation",
        lambda: sm._discount_multiplier(player, merchant, selling=selling))
    add("shortage", lambda: eng.world_director.shortage_multiplier(item.id))
    add("market", lambda: eng.market.multiplier(item))
    add("stock", lambda: sm.stock_multiplier(merchant, item.id))
    add("region", lambda: sm.regional_multiplier(merchant, item))
    return out


def factors_line(factors) -> str:
    if not factors:
        return "at base value"
    return "  ".join(f"{lbl} x{m:.2f}" for lbl, m in factors)


def is_junk(item) -> bool:
    """Common misc trinketry worth clearing out — never gear, quest
    items, consumables or crafting stock."""
    # a preset NPC's inventory may hold bare item-NAME strings (not Item
    # objects); those aren't sellable junk — guard so a driven NPC's trade
    # logic doesn't trip on them (George: agent 'str' has no item_type)
    if not hasattr(item, "item_type"):
        return False
    return (item.item_type == ItemType.MISC
            and item.rarity == ItemRarity.COMMON
            and int(getattr(item, "value", 0)) <= JUNK_MAX_VALUE)


def junk_items(player) -> List:
    return [it for it in player.inventory if is_junk(it)]


def affordable_qty(player, unit_price: int, available: int,
                   want: int = BULK) -> int:
    """How many units a bulk buy can actually take — capped by stock,
    the want, and what the purse allows."""
    if unit_price <= 0:
        return min(want, available)
    return max(0, min(want, available, player.gold // unit_price))
