"""M3 — magic-item IMBUING: add magical power to an EXISTING item in place.

The recipe system produces a fresh item and only consumes the base, so it can't
express "make THIS sword flaming". Enchanting is the one new mechanic: over
`data/enchantments.json`, `enchant(engine, item, eid)` merges an enchantment's
deltas straight into the item instance — `equip_bonuses` (summed by
`effects._gather_bonuses`), `damage_kind`, `use_effect`, a name prefix/suffix, a
rarity bump, and a provenance tag in `metadata["enchantments"]`. Persistence is
FREE (every field round-trips through `Item.to_dict/from_dict`), and the combat/
AC pipeline already reads `equip_bonuses`, so an enchanted instance is simply
stronger. Gated on a station (a forge), the enchanting skill level, and reagents.
"""

import json
import os
from typing import List, Tuple

_DATA = os.path.join(os.path.dirname(__file__), "..", "data",
                     "enchantments.json")
_ENCH = None

_RARITY = ["common", "uncommon", "rare", "epic", "legendary"]


def enchantments() -> dict:
    global _ENCH
    if _ENCH is None:
        try:
            with open(_DATA) as f:
                _ENCH = json.load(f)
        except Exception:
            _ENCH = {}
    return _ENCH


def enchantment(eid: str):
    return enchantments().get(eid)


def _item_type(item) -> str:
    t = getattr(item, "item_type", None)
    return getattr(t, "value", str(t))


def applies(item, ench: dict) -> bool:
    return _item_type(item) in (ench.get("applies_to") or [])


def is_enchanted_with(item, eid: str) -> bool:
    tags = (getattr(item, "metadata", None) or {}).get("enchantments", [])
    return eid in tags


def _count(player, item_id: str) -> int:
    return sum(getattr(it, "quantity", 1) for it in player.inventory
              if getattr(it, "id", "") == item_id)


def _consume(player, item_id: str, n: int) -> None:
    left = n
    for it in list(player.inventory):
        if getattr(it, "id", "") != item_id:
            continue
        q = getattr(it, "quantity", 1)
        take = min(q, left)
        if take >= q:
            player.inventory.remove(it)
        else:
            it.quantity = q - take
        left -= take
        if left <= 0:
            break


def _at_station(engine, station: str) -> bool:
    try:
        loc = engine.player_location()
        if loc and (loc.properties or {}).get(station):
            return True
    except Exception:
        pass
    return False


def can_enchant(engine, item, eid: str) -> Tuple[bool, str]:
    ench = enchantment(eid)
    if ench is None:
        return False, "unknown enchantment"
    if not applies(item, ench):
        return False, f"can't enchant a {_item_type(item)} with {ench['name']}"
    if is_enchanted_with(item, eid):
        return False, f"already bears {ench['name']}"
    station = ench.get("station", "forge")
    if not _at_station(engine, station):
        return False, f"needs a {station.replace('_', ' ')}"
    from engine.skill_progression import get_skill_level
    lvl = get_skill_level(engine.player, ench.get("skill", "enchanting"))
    if lvl < ench.get("min_skill", 0):
        return False, f"needs {ench.get('skill')} {ench['min_skill']}"
    for iid, need in (ench.get("reagents") or {}).items():
        if _count(engine.player, iid) < need:
            return False, f"needs {need}× {iid.replace('_', ' ')}"
    return True, ""


def enchant(engine, item, eid: str) -> Tuple[bool, str]:
    """Imbue `item` with enchantment `eid` (mutates the instance in place)."""
    ok, why = can_enchant(engine, item, eid)
    if not ok:
        return False, why
    ench = enchantment(eid)
    for iid, need in (ench.get("reagents") or {}).items():
        _consume(engine.player, iid, need)
    # merge bonuses
    bonuses = dict(getattr(item, "equip_bonuses", None) or {})
    for k, v in (ench.get("bonuses") or {}).items():
        bonuses[k] = bonuses.get(k, 0) + v
    item.equip_bonuses = bonuses
    if ench.get("damage_kind"):
        item.damage_kind = ench["damage_kind"]
    for k, v in (ench.get("use_effect") or {}).items():
        ue = dict(getattr(item, "use_effect", None) or {})
        ue[k] = v
        item.use_effect = ue
    # provenance + a distinct identity (so a stack won't re-merge it)
    meta = dict(getattr(item, "metadata", None) or {})
    meta.setdefault("enchantments", [])
    meta["enchantments"] = list(meta["enchantments"]) + [eid]
    item.metadata = meta
    item.stackable = False
    # name + rarity
    if ench.get("prefix") and ench["prefix"] not in item.name:
        item.name = f"{ench['prefix']} {item.name}"
    elif ench.get("suffix") and ench["suffix"] not in item.name:
        item.name = f"{item.name} {ench['suffix']}"
    cur = getattr(getattr(item, "rarity", None), "value", "common")
    if cur in _RARITY:
        nxt = _RARITY[min(len(_RARITY) - 1, _RARITY.index(cur) + 1)]
        try:
            from items.item import ItemRarity
            item.rarity = ItemRarity(nxt)
        except Exception:
            pass
    # train the enchanter
    try:
        from engine.skill_progression import train_skill
        train_skill(engine, ench.get("skill", "enchanting"),
                    25 + 10 * ench.get("min_skill", 0))
    except Exception:
        pass
    return True, f"You imbue {item.name} with {ench['name']}."


def available_for(engine, item) -> List[str]:
    """Enchantment ids that COULD be applied to `item` here and now (for UI)."""
    return [eid for eid in enchantments()
            if can_enchant(engine, item, eid)[0]]


def all_applicable(item) -> List[str]:
    """Every enchantment whose type matches `item` (ignoring gates), for menus."""
    return [eid for eid, e in enchantments().items()
            if applies(item, e) and not is_enchanted_with(item, eid)]
