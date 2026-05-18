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
    RING = "ring"
    AMULET = "amulet"
    BOOTS = "boots"
    AMMO = "ammo"
    SCROLL = "scroll"


class ItemRarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


# Damage / element kinds used by weapons + spells
DAMAGE_KINDS = ("slash", "pierce", "bludgeon", "fire", "frost", "lightning",
                "holy", "necrotic", "poison")


@dataclass
class Item:
    """Represents any item in the game.

    See item_registry.py for examples.
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
    # Combat metadata --------------------------------------------------------
    weapon_kind: str = ""          # "" | "melee" | "ranged" | "thrown" | "magic"
    damage_kind: str = "slash"     # entry from DAMAGE_KINDS
    ammo_type: str = ""            # "arrow" | "bolt" | "stone" | ""
    two_handed: bool = False
    # Equipment effect bonuses (applied while item is worn)
    # Recognized keys: strength, dexterity, constitution, intelligence,
    # wisdom, charisma, max_hp, max_mana, armor, hp_regen, mana_regen
    equip_bonuses: Dict[str, int] = field(default_factory=dict)
    # On-use payload (for SCROLLs / consumables): {"spell": id} or
    # {"effect": "blessed", "duration": 5}
    use_effect: Dict[str, Any] = field(default_factory=dict)
    # Free-form payload (rune tags, quest links, …)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ---------------- type predicates --------------------------------------

    def is_consumable(self) -> bool:
        return self.item_type in (ItemType.CONSUMABLE, ItemType.SCROLL)

    def is_weapon(self) -> bool:
        return self.item_type == ItemType.WEAPON

    def is_ranged_weapon(self) -> bool:
        return self.is_weapon() and self.weapon_kind in ("ranged", "thrown")

    def is_melee_weapon(self) -> bool:
        return self.is_weapon() and self.weapon_kind in ("", "melee")

    def is_armor(self) -> bool:
        return self.item_type in (ItemType.ARMOR, ItemType.SHIELD)

    def is_ammo(self) -> bool:
        return self.item_type == ItemType.AMMO

    def is_jewelry(self) -> bool:
        return self.item_type in (ItemType.RING, ItemType.AMULET,
                                  ItemType.BOOTS)

    def is_scroll(self) -> bool:
        return self.item_type == ItemType.SCROLL

    def is_equippable(self) -> bool:
        return self.item_type in (
            ItemType.WEAPON, ItemType.ARMOR, ItemType.SHIELD,
            ItemType.RING, ItemType.AMULET, ItemType.BOOTS,
        )

    # ---------------- serialization ----------------------------------------

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
            "weapon_kind": self.weapon_kind,
            "damage_kind": self.damage_kind,
            "ammo_type": self.ammo_type,
            "two_handed": self.two_handed,
            "equip_bonuses": dict(self.equip_bonuses),
            "use_effect": dict(self.use_effect),
            "metadata": dict(self.metadata),
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
            weapon_kind=d.get("weapon_kind", ""),
            damage_kind=d.get("damage_kind", "slash"),
            ammo_type=d.get("ammo_type", ""),
            two_handed=d.get("two_handed", False),
            equip_bonuses=dict(d.get("equip_bonuses", {})),
            use_effect=dict(d.get("use_effect", {})),
            metadata=dict(d.get("metadata", {})),
        )

    def copy(self) -> "Item":
        return Item.from_dict(self.to_dict())

    def __str__(self) -> str:
        if self.stackable and self.quantity > 1:
            return f"{self.name} x{self.quantity}"
        return self.name
