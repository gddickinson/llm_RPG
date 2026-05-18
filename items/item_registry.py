"""Predefined item registry.

Use `create_item(id)` to spawn a fresh copy of a registry item.
"""

import logging
from typing import Dict, List, Optional

from items.item import Item, ItemType, ItemRarity

logger = logging.getLogger("llm_rpg.items.registry")


def _w(id, name, dmg, value, rarity=ItemRarity.COMMON, desc="",
       weapon_kind="melee", damage_kind="slash", ammo_type="",
       two_handed=False, equip_bonuses=None):
    return Item(id=id, name=name, item_type=ItemType.WEAPON,
                damage=dmg, value=value, rarity=rarity, description=desc,
                weapon_kind=weapon_kind, damage_kind=damage_kind,
                ammo_type=ammo_type, two_handed=two_handed,
                equip_bonuses=dict(equip_bonuses or {}))


def _a(id, name, armor, value, rarity=ItemRarity.COMMON, desc="",
       shield=False, equip_bonuses=None):
    t = ItemType.SHIELD if shield else ItemType.ARMOR
    return Item(id=id, name=name, item_type=t, armor=armor, value=value,
                rarity=rarity, description=desc,
                equip_bonuses=dict(equip_bonuses or {}))


def _c(id, name, heal, value, desc=""):
    return Item(id=id, name=name, item_type=ItemType.CONSUMABLE,
                heal_amount=heal, value=value, description=desc,
                stackable=True)


def _m(id, name, value, desc="", rarity=ItemRarity.COMMON, stackable=True):
    return Item(id=id, name=name, item_type=ItemType.MISC,
                value=value, description=desc, rarity=rarity, stackable=stackable)


def _ring(id, name, value, bonuses, desc="", rarity=ItemRarity.UNCOMMON):
    return Item(id=id, name=name, item_type=ItemType.RING,
                value=value, description=desc, rarity=rarity,
                equip_bonuses=dict(bonuses))


def _amulet(id, name, value, bonuses, desc="", rarity=ItemRarity.UNCOMMON):
    return Item(id=id, name=name, item_type=ItemType.AMULET,
                value=value, description=desc, rarity=rarity,
                equip_bonuses=dict(bonuses))


def _boots(id, name, value, bonuses, desc="", rarity=ItemRarity.UNCOMMON):
    return Item(id=id, name=name, item_type=ItemType.BOOTS,
                value=value, description=desc, rarity=rarity,
                equip_bonuses=dict(bonuses))


def _ammo(id, name, ammo_type, value, qty=20, desc=""):
    return Item(id=id, name=name, item_type=ItemType.AMMO,
                value=value, description=desc, ammo_type=ammo_type,
                stackable=True, quantity=qty)


def _scroll(id, name, value, spell_id, desc="", rarity=ItemRarity.UNCOMMON):
    return Item(id=id, name=name, item_type=ItemType.SCROLL,
                value=value, description=desc, rarity=rarity,
                use_effect={"spell": spell_id}, stackable=True)


ITEM_REGISTRY: Dict[str, Item] = {
    # Weapons -----------------------------------------------------------------
    "dagger": _w("dagger", "Iron Dagger", dmg=3, value=10,
                 weapon_kind="melee", damage_kind="pierce",
                 desc="A short, sharp blade."),
    "sword": _w("sword", "Iron Sword", dmg=6, value=30,
                weapon_kind="melee", damage_kind="slash",
                desc="A reliable steel sword."),
    "longsword": _w("longsword", "Longsword", dmg=8, value=60,
                    weapon_kind="melee", damage_kind="slash",
                    rarity=ItemRarity.UNCOMMON,
                    desc="A well-balanced longsword."),
    "battleaxe": _w("battleaxe", "Battleaxe", dmg=9, value=70,
                    weapon_kind="melee", damage_kind="slash",
                    two_handed=True, rarity=ItemRarity.UNCOMMON,
                    desc="A two-handed axe."),
    "crude_axe": _w("crude_axe", "Crude Axe", dmg=5, value=8,
                    weapon_kind="melee", damage_kind="slash",
                    desc="A roughly-made axe."),
    "warhammer": _w("warhammer", "Warhammer", dmg=10, value=80,
                    weapon_kind="melee", damage_kind="bludgeon",
                    two_handed=True, rarity=ItemRarity.UNCOMMON),
    "staff": _w("staff", "Wizard's Staff", dmg=4, value=40,
                weapon_kind="melee", damage_kind="bludgeon",
                rarity=ItemRarity.UNCOMMON,
                desc="Channels arcane energy.",
                equip_bonuses={"max_mana": 3}),
    "bow": _w("bow", "Hunting Bow", dmg=5, value=35,
              weapon_kind="ranged", damage_kind="pierce",
              ammo_type="arrow",
              desc="A simple ranged weapon."),
    "longbow": _w("longbow", "Longbow", dmg=7, value=70,
                  weapon_kind="ranged", damage_kind="pierce",
                  ammo_type="arrow", two_handed=True,
                  rarity=ItemRarity.UNCOMMON,
                  desc="A long, powerful bow."),
    "crossbow": _w("crossbow", "Crossbow", dmg=8, value=90,
                   weapon_kind="ranged", damage_kind="pierce",
                   ammo_type="bolt", two_handed=True,
                   rarity=ItemRarity.UNCOMMON,
                   desc="A heavy crossbow. Powerful but slow."),
    "sling": _w("sling", "Sling", dmg=2, value=8,
                weapon_kind="ranged", damage_kind="bludgeon",
                ammo_type="stone",
                desc="A simple sling. Uses any small stone."),
    "thrown_knife": _w("thrown_knife", "Throwing Knife", dmg=3, value=12,
                       weapon_kind="thrown", damage_kind="pierce",
                       desc="A balanced blade made for throwing."),
    "silver_blade": _w("silver_blade", "Silver Blade", dmg=7, value=200,
                       weapon_kind="melee", damage_kind="slash",
                       rarity=ItemRarity.RARE,
                       desc="A masterwork silver blade — devastating to monsters."),
    "flaming_sword": _w("flaming_sword", "Flaming Sword", dmg=8, value=400,
                        weapon_kind="melee", damage_kind="fire",
                        rarity=ItemRarity.RARE,
                        desc="A blade wreathed in flame.",
                        equip_bonuses={"damage": 2}),
    "frost_dagger": _w("frost_dagger", "Frost Dagger", dmg=4, value=180,
                       weapon_kind="melee", damage_kind="frost",
                       rarity=ItemRarity.UNCOMMON,
                       desc="The hilt is ice-cold to the touch.",
                       equip_bonuses={"damage": 1}),
    "holy_mace": _w("holy_mace", "Holy Mace", dmg=6, value=160,
                    weapon_kind="melee", damage_kind="holy",
                    rarity=ItemRarity.UNCOMMON,
                    desc="A mace blessed by clerics.",
                    equip_bonuses={"damage": 1, "wisdom": 1}),

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

    # Ammunition -----------------------------------------------------------
    "arrow": _ammo("arrow", "Arrows", "arrow", value=1, qty=20,
                   desc="A bundle of arrows for a bow."),
    "bolt": _ammo("bolt", "Crossbow Bolts", "bolt", value=2, qty=20,
                  desc="Heavy bolts for a crossbow."),
    "stone": _ammo("stone", "Sling Stones", "stone", value=0, qty=20,
                   desc="Smooth stones for a sling."),

    # Rings ----------------------------------------------------------------
    "ring_strength": _ring("ring_strength", "Ring of Strength", value=200,
                            bonuses={"strength": 2},
                            desc="A heavy iron band engraved with runes of might."),
    "ring_protection": _ring("ring_protection", "Ring of Protection", value=220,
                              bonuses={"armor": 1},
                              desc="A silver band that wards off harm."),
    "ring_intellect": _ring("ring_intellect", "Ring of Intellect", value=240,
                             bonuses={"intelligence": 2, "max_mana": 3},
                             desc="A copper ring inset with a sapphire."),
    "ring_health": _ring("ring_health", "Ring of Vitality", value=200,
                          bonuses={"constitution": 1, "max_hp": 6},
                          desc="A jade ring that pulses with warmth."),

    # Amulets --------------------------------------------------------------
    "amulet_health": _amulet("amulet_health", "Amulet of Health", value=300,
                              bonuses={"max_hp": 12, "hp_regen": 1},
                              desc="A warm amulet of polished bone."),
    "amulet_mana": _amulet("amulet_mana", "Amulet of Mana", value=320,
                            bonuses={"max_mana": 8, "mana_regen": 1},
                            desc="A crystal amulet that hums faintly."),
    "amulet_warding": _amulet("amulet_warding", "Amulet of Warding", value=280,
                               bonuses={"armor": 2},
                               desc="An iron pendant on a leather cord."),

    # Boots ----------------------------------------------------------------
    "swift_boots": _boots("swift_boots", "Boots of Swiftness", value=260,
                           bonuses={"dexterity": 1, "dodge": 1},
                           desc="Boots that move almost of their own accord."),
    "silent_boots": _boots("silent_boots", "Boots of Silence", value=240,
                            bonuses={"dexterity": 1},
                            desc="Boots that make no sound when worn."),
    "iron_boots": _boots("iron_boots", "Iron Boots", value=120,
                          bonuses={"armor": 1},
                          desc="Heavy iron-shod boots."),

    # Scrolls --------------------------------------------------------------
    "scroll_fireball": _scroll("scroll_fireball", "Scroll of Fireball",
                                value=80, spell_id="fireball",
                                desc="A scroll inscribed with the fireball rune.",
                                rarity=ItemRarity.UNCOMMON),
    "scroll_heal": _scroll("scroll_heal", "Scroll of Healing",
                            value=60, spell_id="heal",
                            desc="A scroll of healing.",
                            rarity=ItemRarity.UNCOMMON),
    "scroll_frost": _scroll("scroll_frost", "Scroll of Frost Ray",
                             value=70, spell_id="frost_ray",
                             desc="A scroll of frost ray.",
                             rarity=ItemRarity.UNCOMMON),
    "scroll_bless": _scroll("scroll_bless", "Scroll of Blessing",
                             value=50, spell_id="bless",
                             desc="A scroll of blessing."),

    # Books (training manuals) --------------------------------------------
    "tome_arcana": Item(id="tome_arcana", name="Tome of Arcana",
                        item_type=ItemType.BOOK, value=180,
                        rarity=ItemRarity.UNCOMMON,
                        description="A heavy tome on arcane theory. +1 INT permanently.",
                        use_effect={"permanent_stat": "intelligence", "amount": 1}),
    "manual_athletics": Item(id="manual_athletics",
                              name="Manual of Combat Drills",
                              item_type=ItemType.BOOK, value=180,
                              rarity=ItemRarity.UNCOMMON,
                              description="Drills for the warrior. +1 STR permanently.",
                              use_effect={"permanent_stat": "strength", "amount": 1}),
    "manual_dexterity": Item(id="manual_dexterity",
                              name="Manual of Reflex",
                              item_type=ItemType.BOOK, value=180,
                              rarity=ItemRarity.UNCOMMON,
                              description="Reflex training. +1 DEX permanently.",
                              use_effect={"permanent_stat": "dexterity", "amount": 1}),

    # Buff potions ---------------------------------------------------------
    "potion_might": Item(id="potion_might", name="Potion of Might",
                          item_type=ItemType.CONSUMABLE, value=60,
                          stackable=True,
                          description="Grants the Blessed status for 6 turns.",
                          use_effect={"effect": "blessed", "duration": 6}),
    "potion_speed": Item(id="potion_speed", name="Potion of Swiftness",
                          item_type=ItemType.CONSUMABLE, value=70,
                          stackable=True,
                          description="Sharpens reflexes. +2 DEX for 8 turns.",
                          use_effect={"temp_stat": "dexterity",
                                      "amount": 2, "duration": 8}),
    "antidote": Item(id="antidote", name="Antidote",
                     item_type=ItemType.CONSUMABLE, value=40,
                     stackable=True,
                     description="Cures poison.",
                     use_effect={"cure": "poisoned"}),
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
