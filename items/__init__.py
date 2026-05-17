"""Item system for LLM-RPG.

Public API:
- Item dataclass, ItemType, ItemRarity
- ITEM_REGISTRY (id -> Item) and create_item() factory
- generate_loot() for combat drops
"""

from items.item import Item, ItemType, ItemRarity
from items.item_registry import ITEM_REGISTRY, create_item, all_item_ids
from items.loot_tables import generate_loot

__all__ = [
    "Item", "ItemType", "ItemRarity",
    "ITEM_REGISTRY", "create_item", "all_item_ids",
    "generate_loot",
]
