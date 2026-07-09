"""Item registry — loaded from `data/items/*.json`.

Content is data-driven: to add or change an item, edit the JSON files
(weapons.json, armor.json, consumables.json, jewelry.json, misc.json,
ammo_scrolls.json, books.json) — no Python required. Each entry only
needs the fields that differ from `Item` defaults.

Use `create_item(id)` to spawn a fresh copy of a registry item.
"""

import logging
from typing import Dict, List, Optional

from items.item import Item
from items.data_loader import load_data_dir, DataError

logger = logging.getLogger("llm_rpg.items.registry")


def _build_registry() -> Dict[str, Item]:
    registry: Dict[str, Item] = {}
    raw = load_data_dir("items")
    for item_id, entry in raw.items():
        entry = dict(entry)
        entry.setdefault("id", item_id)
        if entry["id"] != item_id:
            raise DataError(
                f"Item key '{item_id}' does not match its id "
                f"'{entry['id']}'")
        try:
            registry[item_id] = Item.from_dict(entry)
        except (KeyError, ValueError) as e:
            raise DataError(f"Bad item entry '{item_id}': {e}") from e
    return registry


ITEM_REGISTRY: Dict[str, Item] = _build_registry()


def create_item(item_id: str, quantity: int = 1) -> Optional[Item]:
    """Return a fresh copy of an item from the registry, or None if unknown.

    Callers (engine upgrade pass, etc.) are expected to probe several
    candidate ids; missing entries are logged at debug level, not warning.
    """
    proto = ITEM_REGISTRY.get(item_id)
    if proto is None:
        logger.debug(f"Unknown item id: {item_id}")
        return None
    item = proto.copy()
    if item.stackable:
        item.quantity = quantity
    return item


def all_item_ids() -> List[str]:
    return list(ITEM_REGISTRY.keys())


def item_by_name(name: str) -> Optional[Item]:
    """Find a registry item by name (case-insensitive substring match)."""
    name_l = name.lower()
    # exact first
    for item in ITEM_REGISTRY.values():
        if item.name.lower() == name_l:
            return item.copy()
    # substring
    for item in ITEM_REGISTRY.values():
        if name_l in item.name.lower():
            return item.copy()
    return None
