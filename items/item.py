"""Item dataclass and enums."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    CONSUMABLE = "consumable"
    QUEST = "quest"
    MISC = "misc"
    KEY = "key"
    INGREDIENT = "ingredient"
    BOOK = "book"
    CURRENCY = "currency"


class ItemRarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


@dataclass
class Item:
    """Represents any item in the game.

    Attributes
    ----------
    id : str
        Stable identifier (used for save/load and registry lookup).
    name : str
        Human-readable name.
    item_type : ItemType
    value : int
        Gold value used for buying/selling.
    description : str
    rarity : ItemRarity
    weight : float
        Inventory weight (currently informational).
    damage : int
        For WEAPON — base damage. 0 otherwise.
    armor : int
        For ARMOR/SHIELD — damage reduction.
    heal_amount : int
        For CONSUMABLE — HP restored on use.
    stackable : bool
    quantity : int
    metadata : dict
        Free-form payload (effects, quest links, ...).
    """

    id: str
    name: str
    item_type: ItemType = ItemType.MISC
    value: int = 1
    description: str = ""
    rarity: ItemRarity = ItemRarity.COMMON
    weight: float = 0.0
    damage: int = 0
    armor: int = 0
    heal_amount: int = 0
    stackable: bool = False
    quantity: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_consumable(self) -> bool:
        return self.item_type == ItemType.CONSUMABLE

    def is_weapon(self) -> bool:
        return self.item_type == ItemType.WEAPON

    def is_armor(self) -> bool:
        return self.item_type in (ItemType.ARMOR, ItemType.SHIELD)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "item_type": self.item_type.value,
            "value": self.value,
            "description": self.description,
            "rarity": self.rarity.value,
            "weight": self.weight,
            "damage": self.damage,
            "armor": self.armor,
            "heal_amount": self.heal_amount,
            "stackable": self.stackable,
            "quantity": self.quantity,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Item":
        return cls(
            id=d["id"],
            name=d["name"],
            item_type=ItemType(d.get("item_type", "misc")),
            value=d.get("value", 1),
            description=d.get("description", ""),
            rarity=ItemRarity(d.get("rarity", "common")),
            weight=d.get("weight", 0.0),
            damage=d.get("damage", 0),
            armor=d.get("armor", 0),
            heal_amount=d.get("heal_amount", 0),
            stackable=d.get("stackable", False),
            quantity=d.get("quantity", 1),
            metadata=d.get("metadata", {}),
        )

    def copy(self) -> "Item":
        return Item.from_dict(self.to_dict())

    def __str__(self) -> str:
        if self.stackable and self.quantity > 1:
            return f"{self.name} x{self.quantity}"
        return self.name
