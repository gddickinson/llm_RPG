"""Equipment slots — worn items separate from the inventory bag.

A character has six slots: weapon, armor, shield, amulet, ring, boots.
The combat system queries equipped items (not the entire inventory) for
damage and armor calculations.

Equipping moves an item from inventory to the slot; unequipping does the
reverse. Auto-equip on pickup is opt-in (currently off).
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from items.item import Item, ItemType

logger = logging.getLogger("llm_rpg.equipment")


class EquipSlot(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    AMULET = "amulet"
    RING = "ring"
    BOOTS = "boots"


# Which item types belong in which slot
ITEM_TYPE_TO_SLOT = {
    ItemType.WEAPON: EquipSlot.WEAPON,
    ItemType.ARMOR: EquipSlot.ARMOR,
    ItemType.SHIELD: EquipSlot.SHIELD,
    ItemType.RING: EquipSlot.RING,
    ItemType.AMULET: EquipSlot.AMULET,
    ItemType.BOOTS: EquipSlot.BOOTS,
}


def slot_for_item(item: Item) -> Optional[EquipSlot]:
    return ITEM_TYPE_TO_SLOT.get(item.item_type)


def get_equipment(character) -> Dict[str, Optional[Item]]:
    """Return the character's equipment dict (creates if missing)."""
    eq = getattr(character, "equipment", None)
    if not isinstance(eq, dict):
        eq = {s.value: None for s in EquipSlot}
        character.equipment = eq
    else:
        # Ensure every slot key exists
        for s in EquipSlot:
            eq.setdefault(s.value, None)
    return eq


def is_two_handed(item) -> bool:
    return bool(getattr(item, "two_handed", False))


def equip(character, item: Item) -> str:
    """Move `item` from inventory to its slot. Returns a status
    message. Enforces two-handed weapon rules (P15.10): a two-handed
    weapon needs both hands (any shield is stowed), and a shield
    can't be raised while two hands grip a weapon."""
    slot = slot_for_item(item)
    if slot is None:
        return f"{item.name} can't be equipped."
    if item not in character.inventory:
        return f"You don't have {item.name}."
    eq = get_equipment(character)
    stowed = ""
    if slot is EquipSlot.SHIELD:
        wpn = eq.get("weapon")
        if wpn is not None and is_two_handed(wpn):
            return (f"Both hands grip the {wpn.name} — there's no "
                    f"room for a shield.")
    if slot is EquipSlot.WEAPON and is_two_handed(item):
        shield = eq.get("shield")
        if shield is not None:
            eq["shield"] = None
            character.inventory.append(shield)
            stowed = f" You stow the {shield.name} — both hands " \
                     f"on the {item.name}."
    previous = eq[slot.value]
    eq[slot.value] = item
    character.inventory.remove(item)
    if previous is not None:
        character.inventory.append(previous)
    haunted_note = ""
    try:   # the gear of the dead remembers (P12.13)
        from engine.bones import on_equip_haunted
        haunted_note = on_equip_haunted(character, item) or ""
        if haunted_note:
            haunted_note = " " + haunted_note
    except Exception:
        pass
    if previous is not None:
        return (f"You equip {item.name} (replacing "
                f"{previous.name}).{stowed}{haunted_note}")
    return f"You equip {item.name}.{stowed}{haunted_note}"


def unequip(character, slot: EquipSlot) -> str:
    eq = get_equipment(character)
    item = eq[slot.value]
    if not item:
        return f"Nothing equipped in {slot.value}."
    character.inventory.append(item)
    eq[slot.value] = None
    return f"You unequip {item.name}."


def equipped_weapon(character) -> Optional[Item]:
    return get_equipment(character)["weapon"]


def equipped_shield(character) -> Optional[Item]:
    return get_equipment(character)["shield"]


def equipped_items(character):
    """Return list of all currently-equipped (non-None) items."""
    return [it for it in get_equipment(character).values() if it is not None]


def total_armor(character) -> int:
    """Sum armor + shield bonuses from equipped slots."""
    eq = get_equipment(character)
    total = 0
    for slot in ("armor", "shield"):
        item = eq.get(slot)
        if item:
            total += getattr(item, "armor", 0)
    return total


def armor_set(item):
    """The matched-set tag of a worn piece, or None."""
    return (getattr(item, "metadata", None) or {}).get("armor_set")


def set_bonus(character):
    """A matched armor set rewards discipline (P15.10): 2+ worn
    pieces (armor/shield/boots) sharing a set tag give +1 AC each.
    Returns (bonus, set_name) — (0, None) if nothing matches."""
    eq = get_equipment(character)
    from collections import Counter
    tags = Counter()
    for slot in ("armor", "shield", "boots"):
        it = eq.get(slot)
        tag = armor_set(it) if it else None
        if tag:
            tags[tag] += 1
    if not tags:
        return 0, None
    best, count = tags.most_common(1)[0]
    if count >= 2:
        return count, best
    return 0, None


def weapon_damage(character) -> int:
    weapon = equipped_weapon(character)
    return getattr(weapon, "damage", 0) if weapon else 0


def to_dict(character) -> Dict[str, Optional[Dict]]:
    eq = get_equipment(character)
    return {slot: (it.to_dict() if it else None) for slot, it in eq.items()}


def from_dict(character, data: Dict[str, Optional[Dict]]) -> None:
    eq: Dict[str, Optional[Item]] = {}
    for slot, item_data in data.items():
        if item_data is None:
            eq[slot] = None
        else:
            eq[slot] = Item.from_dict(item_data)
    character.equipment = eq
