"""Predefined item registry.

Use `create_item(id)` to spawn a fresh copy of a registry item.
"""

import logging
from typing import Dict, List, Optional

from items.item import Item, ItemType, ItemRarity

logger = logging.getLogger("llm_rpg.items.registry")


def _w(id, name, dmg, value, rarity=ItemRarity.COMMON, desc=""):
    return Item(id=id, name=name, item_type=ItemType.WEAPON,
                damage=dmg, value=value, rarity=rarity, description=desc)


def _a(id, name, armor, value, rarity=ItemRarity.COMMON, desc="", shield=False):
    t = ItemType.SHIELD if shield else ItemType.ARMOR
    return Item(id=id, name=name, item_type=t, armor=armor, value=value,
                rarity=rarity, description=desc)


def _c(id, name, heal, value, desc=""):
    return Item(id=id, name=name, item_type=ItemType.CONSUMABLE,
                heal_amount=heal, value=value, description=desc,
                stackable=True)


def _m(id, name, value, desc="", rarity=ItemRarity.COMMON, stackable=True):
    return Item(id=id, name=name, item_type=ItemType.MISC,
                value=value, description=desc, rarity=rarity, stackable=stackable)


ITEM_REGISTRY: Dict[str, Item] = {
    # Weapons -----------------------------------------------------------------
    "dagger": _w("dagger", "Iron Dagger", dmg=3, value=10,
                 desc="A short, sharp blade."),
    "sword": _w("sword", "Iron Sword", dmg=6, value=30,
                desc="A reliable steel sword."),
    "longsword": _w("longsword", "Longsword", dmg=8, value=60,
                    rarity=ItemRarity.UNCOMMON,
                    desc="A well-balanced longsword."),
    "battleaxe": _w("battleaxe", "Battleaxe", dmg=9, value=70,
                    rarity=ItemRarity.UNCOMMON,
                    desc="A two-handed axe."),
    "crude_axe": _w("crude_axe", "Crude Axe", dmg=5, value=8,
                    desc="A roughly-made axe."),
    "warhammer": _w("warhammer", "Warhammer", dmg=10, value=80,
                    rarity=ItemRarity.UNCOMMON),
    "staff": _w("staff", "Wizard's Staff", dmg=4, value=40,
                rarity=ItemRarity.UNCOMMON,
                desc="Channels arcane energy."),
    "bow": _w("bow", "Hunting Bow", dmg=5, value=35,
              desc="A simple ranged weapon."),
    "silver_blade": _w("silver_blade", "Silver Blade", dmg=7, value=200,
                       rarity=ItemRarity.RARE,
                       desc="A masterwork silver blade — devastating to monsters."),

    # Armor ------------------------------------------------------------------
    "leather": _a("leather", "Leather Armor", armor=2, value=25,
                  desc="Light, flexible protection."),
    "chainmail": _a("chainmail", "Chainmail", armor=4, value=80,
                    rarity=ItemRarity.UNCOMMON,
                    desc="Interlocking metal rings."),
    "plate": _a("plate", "Plate Armor", armor=6, value=200,
                rarity=ItemRarity.RARE),
    "tattered_armor": _a("tattered_armor", "Tattered Armor", armor=1, value=5,
                         desc="Better than nothing."),
    "shield": _a("shield", "Wooden Shield", armor=2, value=15, shield=True),
    "iron_shield": _a("iron_shield", "Iron Shield", armor=3, value=40, shield=True,
                      rarity=ItemRarity.UNCOMMON),

    # Consumables ------------------------------------------------------------
    "potion": _c("potion", "Healing Potion", heal=15, value=20,
                 desc="Restores 15 HP."),
    "greater_potion": _c("greater_potion", "Greater Healing Potion", heal=40,
                         value=80, desc="Restores 40 HP."),
    "bandage": _c("bandage", "Bandage", heal=5, value=5,
                  desc="A simple field dressing."),
    "ale": _c("ale", "Tankard of Ale", heal=2, value=3,
              desc="A frothy ale. Restores 2 HP."),
    "mead": _c("mead", "Mead", heal=3, value=5),
    "bread": _c("bread", "Loaf of Bread", heal=4, value=4),
    "jerky": _c("jerky", "Dried Jerky", heal=3, value=4),
    "wine": _c("wine", "Bottle of Wine", heal=4, value=10),

    # Misc / quest -----------------------------------------------------------
    "lockpicks": _m("lockpicks", "Set of Lockpicks", value=15,
                    desc="For the right kind of work."),
    "spellbook": _m("spellbook", "Tome of Arcana", value=80,
                    rarity=ItemRarity.UNCOMMON,
                    desc="Pages crackle with latent magic."),
    "holy_symbol": _m("holy_symbol", "Holy Symbol", value=25),
    "ledger": _m("ledger", "Merchant's Ledger", value=2),
    "coins": _m("coins", "Bag of Coins", value=10, stackable=True),
    "lute": _m("lute", "Lute", value=50, desc="A finely-crafted lute."),
    "flute": _m("flute", "Wooden Flute", value=15),
    "whistle": _m("whistle", "Guard Whistle", value=5),
    "goods": _m("goods", "Trade Goods", value=15),
    "personal_items": _m("personal_items", "Personal Effects", value=2),
    "stolen_jewelry": _m("stolen_jewelry", "Stolen Jewelry", value=120,
                         rarity=ItemRarity.UNCOMMON,
                         desc="Engraved with an unfamiliar crest."),
    "troll_tooth": _m("troll_tooth", "Troll Tooth", value=50,
                      rarity=ItemRarity.UNCOMMON,
                      desc="Proof of a slain troll. Useful for quests."),
    "wolf_pelt": _m("wolf_pelt", "Wolf Pelt", value=20),
    "herb_bundle": Item(id="herb_bundle", name="Bundle of Herbs",
                        item_type=ItemType.INGREDIENT, value=12,
                        description="Healing herbs gathered in the forest.",
                        stackable=True),
    "old_map": _m("old_map", "Old Map", value=30,
                  rarity=ItemRarity.UNCOMMON,
                  desc="Faded ink hints at hidden ruins."),
    "rusty_key": Item(id="rusty_key", name="Rusty Key",
                      item_type=ItemType.KEY, value=2,
                      description="Opens some old, forgotten door."),
}


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
