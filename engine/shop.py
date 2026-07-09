"""Merchant shop catalog + faction-aware pricing.

Each merchant NPC gets a categorized inventory of items they sell, refreshed
periodically. Buy / sell uses these prices and may apply discounts based on
the player's reputation with the merchant's faction.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from items.item import Item
from items.item_registry import create_item

logger = logging.getLogger("llm_rpg.shop")


# Merchant categories by NPC id pattern / name keyword — loaded from
# data/shop_catalogs.json. Each entry: list of item ids (repeats = extra
# stock). Buy price is item.value * rep multiplier; sell is value//2.
def _build_catalogs() -> Dict[str, List[str]]:
    from items.data_loader import load_data_file
    return {cat: list(ids)
            for cat, ids in load_data_file("shop_catalogs.json").items()}


SHOP_CATALOGS: Dict[str, List[str]] = _build_catalogs()


@dataclass
class ShopCatalog:
    """Per-merchant snapshot of items for sale."""
    merchant_id: str
    items: List[Item] = field(default_factory=list)
    last_refreshed_minute: int = 0


def _category_for_npc(npc) -> str:
    """Map an NPC to a shop category string."""
    nid = (npc.id or "").lower()
    name = (npc.name or "").lower()
    home = (getattr(npc, "home_location", "") or "").lower()
    klass = getattr(npc.character_class, "value", "").lower()

    # Specific NPC ids
    if "tavern" in nid or "innkeeper" in nid or "tavern" in home or \
            "inn" in home:
        return "tavern"
    if "blacksmith" in nid or "smith" in nid:
        return "blacksmith"
    if "wheelwright" in nid:
        return "wheelwright"
    if "priest" in nid or "cleric" in nid or "chapel" in home or \
            "temple" in home:
        return "cleric"
    if "wizard" in nid or klass == "wizard":
        return "wizard"
    if klass == "ranger":
        return "ranger"
    if klass == "merchant" and "store" in home:
        return "general"
    if klass == "cleric":
        return "cleric"
    return "general"


class ShopManager:
    """Owns the per-NPC shop catalogs."""

    def __init__(self, engine):
        self.engine = engine
        self.catalogs: Dict[str, ShopCatalog] = {}

    def catalog_for(self, npc) -> ShopCatalog:
        cat = self.catalogs.get(npc.id)
        if cat is None:
            cat = ShopCatalog(merchant_id=npc.id)
            self._stock(cat, npc)
            self.catalogs[npc.id] = cat
        return cat

    def _stock(self, cat: ShopCatalog, npc) -> None:
        category = _category_for_npc(npc)
        ids = SHOP_CATALOGS.get(category, SHOP_CATALOGS["general"])
        items = []
        for item_id in ids:
            item = create_item(item_id, quantity=20 if item_id in
                               ("arrow", "bolt", "stone") else 1)
            if item:
                items.append(item)
        cat.items = items
        cat.last_refreshed_minute = self.engine.world.time

    def refresh_all_if_due(self, minutes_between: int = 24 * 60) -> None:
        now = self.engine.world.time
        for npc_id, cat in self.catalogs.items():
            if (now - cat.last_refreshed_minute) >= minutes_between:
                npc = self.engine.npc_manager.get_npc(npc_id)
                if npc is not None:
                    self._stock(cat, npc)

    # ----- persistence ---------------------------------------------------

    def to_dict(self) -> Dict:
        return {
            npc_id: {
                "items": [it.to_dict() for it in cat.items],
                "last_refreshed_minute": cat.last_refreshed_minute,
            }
            for npc_id, cat in self.catalogs.items()
        }

    def from_dict(self, data: Dict) -> None:
        self.catalogs = {}
        for npc_id, cd in data.items():
            cat = ShopCatalog(merchant_id=npc_id)
            cat.items = [Item.from_dict(it) for it in cd.get("items", [])]
            cat.last_refreshed_minute = cd.get("last_refreshed_minute", 0)
            self.catalogs[npc_id] = cat

    # ----- price computation -------------------------------------------

    def buy_price(self, player, item: Item, merchant_npc) -> int:
        """Player buys at this price."""
        base = max(1, int(item.value))
        mult = self._discount_multiplier(player, merchant_npc, selling=False)
        return max(1, int(round(base * mult)))

    def sell_price(self, player, item: Item, merchant_npc) -> int:
        """Player sells at this price (merchant pays)."""
        base = max(1, int(item.value) // 2)
        mult = self._discount_multiplier(player, merchant_npc, selling=True)
        return max(1, int(round(base * mult)))

    def _discount_multiplier(self, player, merchant_npc,
                             selling: bool = False) -> float:
        """Compute price multiplier based on faction rep + relationship.

        Friendly merchant -> player buys cheaper / sells dearer.
        Hostile merchant  -> player buys more expensive / sells cheaper.
        """
        try:
            from characters.factions import Faction, get_rep, faction_of_class
            klass = getattr(merchant_npc.character_class, "value", "")
            fac = faction_of_class(klass)
            if fac == Faction.NEUTRAL:
                fac_score = 0
            else:
                fac_score = get_rep(player, fac)
        except Exception:
            fac_score = 0

        # Personal relationship
        rel = 0
        try:
            rel = merchant_npc.get_relationship(player.id)
        except Exception:
            pass

        # Combined score in [-100..+100]
        combined = max(-100, min(100, (fac_score + rel) // 2))
        # Discount: at +50 score, prices are 0.85x for buying, 1.15x for selling
        # at -50, 1.20x for buying, 0.80x for selling
        delta = (combined / 100.0) * 0.20    # +-0.20
        if selling:
            return 1.0 + delta            # higher rep = higher sell price
        return 1.0 - delta                # higher rep = lower buy price


def merchants_near(engine, player, radius: float = 2.0):
    """Return a list of adjacent merchant NPCs (for opening a shop)."""
    out = []
    px, py = player.position
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        klass = getattr(npc.character_class, "value", "")
        if klass not in ("merchant", "cleric", "wizard", "ranger"):
            continue
        d = ((npc.position[0] - px) ** 2 + (npc.position[1] - py) ** 2) ** 0.5
        if d <= radius:
            out.append(npc)
    return out
