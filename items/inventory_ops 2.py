"""P25.1 — stackable-item grouping for inventories.

Identical STACKABLE items (arrows, ammo, potions, gathered raws) MERGE into a
single inventory slot carrying a `quantity`, instead of piling up as many
single-item slots (the P25.1 bug). `stack_add` is a safe drop-in for
`inventory.append` at the item-ACQUISITION sites: a non-stackable item — or a
stackable one that differs in any identity field (a STOLEN, enchanted, or
quest-tagged instance) — always takes its own slot, so distinct instances never
silently merge. Load paths keep raw append (the saved stacks already carry the
right `quantity`).
"""


def can_stack(a, b) -> bool:
    """Whether items `a` and `b` may occupy the same stack — both stackable and
    identical in every identity field (per-instance state kept distinct)."""
    if not (getattr(a, "stackable", False) and getattr(b, "stackable", False)):
        return False
    return (getattr(a, "id", None) == getattr(b, "id", None)
            and getattr(a, "name", None) == getattr(b, "name", None)
            and getattr(a, "item_type", None) == getattr(b, "item_type", None)
            and getattr(a, "rarity", None) == getattr(b, "rarity", None)
            and (getattr(a, "use_effect", None) or {})
            == (getattr(b, "use_effect", None) or {})
            and (getattr(a, "metadata", None) or {})
            == (getattr(b, "metadata", None) or {})
            and (getattr(a, "equip_bonuses", None) or {})
            == (getattr(b, "equip_bonuses", None) or {}))


def find_stack(inventory, item):
    """The existing item in `inventory` that `item` would merge onto, or None."""
    if not getattr(item, "stackable", False):
        return None
    for inv in inventory:
        if can_stack(inv, item):
            return inv
    return None


def stack_add(inventory, item) -> bool:
    """Add `item` to `inventory`, MERGING into a matching stack when possible.
    Returns True if it merged into an existing stack (added NO new slot), False
    if it was appended as a new slot."""
    stack = find_stack(inventory, item)
    if stack is not None:
        stack.quantity = (getattr(stack, "quantity", 1)
                          + getattr(item, "quantity", 1))
        return True
    inventory.append(item)
    return False
