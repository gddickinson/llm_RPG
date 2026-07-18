"""Loot drop tables.

Given a defeated character (or just class+level), produce a list of
items to drop on the ground.
"""

import logging
import random
from typing import Any, List

from items.item import Item
from items.item_registry import create_item

logger = logging.getLogger("llm_rpg.items.loot")


# Map character class value -> list of (item_id, weight)
LOOT_BY_CLASS = {
    "brigand": [
        ("crude_axe", 3),
        ("dagger", 2),
        ("tattered_armor", 2),
        ("coins", 5),
        ("stolen_jewelry", 1),
        ("potion", 2),
    ],
    "troll": [
        ("crude_axe", 3),
        ("tattered_armor", 1),
        ("troll_tooth", 4),
        ("stolen_jewelry", 2),
        ("coins", 3),
    ],
    "monster": [
        ("wolf_pelt", 4),
        ("coins", 2),
    ],
    "warrior": [
        ("sword", 3),
        ("leather", 2),
        ("shield", 2),
        ("potion", 2),
        ("coins", 3),
    ],
    "guard": [
        ("sword", 4),
        ("chainmail", 1),
        ("shield", 2),
        ("whistle", 1),
        ("coins", 2),
    ],
    "wizard": [
        ("staff", 2),
        ("spellbook", 1),
        ("potion", 3),
        ("greater_potion", 1),
        ("coins", 2),
    ],
    "rogue": [
        ("dagger", 3),
        ("lockpicks", 2),
        ("leather", 1),
        ("coins", 4),
    ],
    "cleric": [
        ("holy_symbol", 1),
        ("potion", 4),
        ("bandage", 3),
        ("coins", 2),
    ],
    "merchant": [
        ("goods", 4),
        ("ledger", 1),
        ("coins", 5),
    ],
    "bard": [
        ("lute", 1),
        ("flute", 2),
        ("wine", 2),
        ("coins", 2),
    ],
    "villager": [
        ("bread", 3),
        ("personal_items", 4),
        ("coins", 1),
    ],
}

# Generic fallback table
DEFAULT_LOOT = [
    ("coins", 3),
    ("bread", 2),
    ("personal_items", 1),
]

# T1.1b level-scaled gear tiers — a strong / elite / boss foe has a chance to also
# drop a quality item from the tier its level warrants, so beating hard things is
# the loot-chase reward (the "power from gear" axis the steep-ish curve assumes).
TIER_LOOT = {
    "uncommon": [("chainmail", 3), ("brigandine", 3), ("banded_mail", 3),
                 ("iron_shield", 2)],
    "rare": [("plate", 3), ("fortified_plate", 3), ("steel_shield", 2),
             ("guardian_halberd", 1)],
    "epic": [("dragonscale_mail", 2), ("sunderer", 2), ("titans_maul", 2),
             ("stormcaller_bow", 2)],
    "legendary": [("aegis_of_dawn", 1), ("doombringer", 1)],
}


def _weighted_choice(table, rng):
    total = sum(w for _, w in table)
    if total <= 0:
        return None
    pick = rng.uniform(0, total)
    upto = 0.0
    for item_id, weight in table:
        upto += weight
        if upto >= pick:
            return item_id
    return table[-1][0]


def _bonus_gear(character, rng):
    """T1.1b: a chance for a strong/elite/boss foe to drop a QUALITY gear item from
    a tier scaled by its effective level. Returns an Item or None."""
    level = getattr(character, "level", 1) or 1
    meta = getattr(character, "metadata", None) or {}
    elite = bool(meta.get("elite") or meta.get("boss") or meta.get("nemesis_id"))
    eff = level + (4 if elite else 0)
    if rng.random() > min(0.55, 0.03 * eff):        # scarce, scaling with power
        return None
    if eff >= 12:
        tier = rng.choice(("epic", "epic", "legendary", "rare"))
    elif eff >= 8:
        tier = rng.choice(("rare", "rare", "epic"))
    elif eff >= 4:
        tier = rng.choice(("uncommon", "rare"))
    else:
        tier = "uncommon"
    item_id = _weighted_choice(TIER_LOOT.get(tier, []), rng)
    return create_item(item_id) if item_id else None


def generate_loot(character: Any, rng: random.Random = None,
                  drop_count: int = None) -> List[Item]:
    """Roll loot for a defeated character.

    Parameters
    ----------
    character : Character
        Defeated character (uses .character_class, .level).
    rng : random.Random
        Optional RNG for reproducible drops.
    drop_count : int
        How many items to drop. Default: 1 + level // 3.
    """
    rng = rng or random.Random()
    # a per-creature loot table wins (P32.3 wildlife carry their own drops —
    # a deer yields meat + hide, not a wolf pelt); else fall back to the class
    meta = getattr(character, "metadata", None) or {}
    custom = meta.get("loot_table")
    if custom:
        table = [tuple(e) if isinstance(e, (list, tuple)) else (e, 1)
                 for e in custom]
    else:
        klass = getattr(getattr(character, "character_class", None),
                        "value", "villager")
        table = LOOT_BY_CLASS.get(klass, DEFAULT_LOOT)

    if drop_count is None:
        level = getattr(character, "level", 1)
        drop_count = 1 + max(0, level // 3)

    drops = []
    for _ in range(drop_count):
        item_id = _weighted_choice(table, rng)
        if not item_id:
            continue
        item = create_item(item_id)
        if item:
            drops.append(item)

    bonus = _bonus_gear(character, rng)             # T1.1b quality gear drop
    if bonus is not None:
        drops.append(bonus)

    return drops
