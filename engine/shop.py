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
    gold: int = 0  # merchant's buying budget; refills on restock


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


def _load_regional():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "data" / \
        "settlement_economy.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


REGIONAL = _load_regional()      # settlement -> category factors
STOCK_K = 0.05                   # price move per unit of deviation
STOCK_CLAMP = (0.5, 2.0)
HAGGLE_PATIENCE = 3
HAGGLE_CAP = 0.15


def settlement_of(engine, x: int, y: int) -> str:
    best, best_d = "the wilds", None
    for loc in engine.world.locations:
        if not any(k in loc.name for k in ("Village", "Hamlet",
                                           "Camp")):
            continue
        d = abs(loc.x + loc.width // 2 - x) + \
            abs(loc.y + loc.height // 2 - y)
        if best_d is None or d < best_d:
            best, best_d = loc.name, d
    return best


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
        # Buying budget scales with the shop's wares; refills each restock
        cat.gold = 100 + sum(it.value for it in items) // 4

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
                "gold": cat.gold,
            }
            for npc_id, cat in self.catalogs.items()
        }

    def from_dict(self, data: Dict) -> None:
        self.catalogs = {}
        for npc_id, cd in data.items():
            cat = ShopCatalog(merchant_id=npc_id)
            cat.items = [Item.from_dict(it) for it in cd.get("items", [])]
            cat.last_refreshed_minute = cd.get("last_refreshed_minute", 0)
            cat.gold = cd.get("gold", 150)
            self.catalogs[npc_id] = cat

    # ----- P12.10: stock elasticity + regional supply ---------------

    def stock_multiplier(self, merchant_npc, item_id: str) -> float:
        """OSRS: price moves STOCK_K per unit the shop's stock
        deviates from its baseline. Restock self-heals daily."""
        cat = self.catalog_for(merchant_npc)
        category = _category_for_npc(merchant_npc)
        ids = SHOP_CATALOGS.get(category, SHOP_CATALOGS["general"])
        base = max(1, ids.count(item_id))
        current = sum(1 for it in cat.items if it.id == item_id)
        mult = 1.0 - STOCK_K * (current - base)
        return max(STOCK_CLAMP[0], min(STOCK_CLAMP[1], mult))

    def regional_multiplier(self, merchant_npc, item: Item) -> float:
        """M&B: settlements are cheap in what they make, dear in
        what they lack — buy low here, sell high there."""
        try:
            from engine.market import category_of
            home = settlement_of(self.engine, *merchant_npc.position)
            return float(REGIONAL.get(home, {}).get(
                category_of(item), 1.0))
        except Exception:
            return 1.0

    # ----- P12.10: the haggle-patience minigame ---------------------

    def haggle_state(self, player, merchant_npc) -> dict:
        day = self.engine.world.time // (24 * 60)
        meta = merchant_npc.metadata
        if meta.get("haggle_day") != day:
            meta["haggle_day"] = day
            meta["haggle_patience"] = HAGGLE_PATIENCE
        deals = player.metadata.setdefault("haggle_deal", {})
        deal = deals.get(merchant_npc.id, {})
        if deal.get("day") != day:
            deal = {"day": day, "discount": 0.0}
            deals[merchant_npc.id] = deal
        return {"patience": meta["haggle_patience"],
                "discount": deal["discount"]}

    def haggle(self, player, merchant_npc) -> str:
        """One push at the price. Patience is finite and personal."""
        state = self.haggle_state(player, merchant_npc)
        if state["patience"] <= 0:
            return (f"{merchant_npc.name} is done haggling with "
                    f"you today.")
        if state["discount"] >= HAGGLE_CAP:
            return f"{merchant_npc.name} won't budge another copper."
        from engine.skills import Degree, Skill, check
        result = check(player, Skill.PERSUASION, dc=13,
                       rng=self.engine.combat_system.rng)
        deal = player.metadata["haggle_deal"][merchant_npc.id]
        meta = merchant_npc.metadata
        if result.degree is Degree.CRIT_SUCCESS:
            deal["discount"] = min(HAGGLE_CAP,
                                   deal["discount"] + 0.10)
            msg = (f"{merchant_npc.name} laughs and knocks the "
                   f"price down ({int(deal['discount'] * 100)}% off).")
        elif result.success:
            deal["discount"] = min(HAGGLE_CAP,
                                   deal["discount"] + 0.05)
            msg = (f"A nod — {int(deal['discount'] * 100)}% off "
                   f"today.")
        elif result.degree is Degree.CRIT_FAIL:
            meta["haggle_patience"] = 0
            merchant_npc.modify_relationship(player.id, -5)
            msg = (f"{merchant_npc.name} bristles: \"Buy it or "
                   f"leave.\" (They'll remember the insult.)")
        else:
            meta["haggle_patience"] -= 1
            msg = (f"{merchant_npc.name} shakes their head. "
                   f"(patience {meta['haggle_patience']}/"
                   f"{HAGGLE_PATIENCE})")
        self.engine.memory_manager.add_event(msg)
        return msg

    def trade_refusal(self, player, merchant_npc):
        """Despised customers get the door, not a price (P12.11)."""
        try:
            from characters.factions import (Faction, threshold,
                                             faction_of_class)
            klass = getattr(merchant_npc.character_class, "value", "")
            fac = faction_of_class(klass)
            if fac != Faction.NEUTRAL and \
                    threshold(player, fac) == "despised":
                return (f"{merchant_npc.name} folds their arms: "
                        f"\"Your coin's no good here. OUT.\"")
        except Exception:
            pass
        return None

    # ----- price computation -------------------------------------------

    def buy_price(self, player, item: Item, merchant_npc) -> int:
        """Player buys at this price."""
        base = max(1, int(item.value))
        mult = self._discount_multiplier(player, merchant_npc, selling=False)
        try:
            mult *= self.engine.world_director.shortage_multiplier(item.id)
        except Exception:
            pass
        try:
            mult *= self.engine.market.multiplier(item)   # P8.5
        except Exception:
            pass
        try:   # P12.10: stock + region shape the price
            mult *= self.stock_multiplier(merchant_npc, item.id)
            mult *= self.regional_multiplier(merchant_npc, item)
        except Exception:
            pass
        return max(1, int(round(base * mult)))

    def sell_price(self, player, item: Item, merchant_npc) -> int:
        """Player sells at this price (merchant pays)."""
        base = max(1, int(item.value) // 2)
        mult = self._discount_multiplier(player, merchant_npc, selling=True)
        try:
            mult *= self.engine.market.multiplier(item)   # P8.5
        except Exception:
            pass
        try:   # P12.10: gluts pay less; scarce regions pay more
            mult *= self.stock_multiplier(merchant_npc, item.id)
            mult *= self.regional_multiplier(merchant_npc, item)
        except Exception:
            pass
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

        # Regional diary tiers stack a further discount on purchases
        diary = 0.0
        try:
            diary = self.engine.diary_manager.discount_for_merchant(
                merchant_npc)
        except Exception:
            pass

        # Haggling: the P12.10 patience minigame's earned deal
        # (a won /persuade still grants the old 20% token; take max)
        haggle = 0.0
        try:
            if self.engine.persuasion.haggle_active(merchant_npc):
                haggle = 0.20
        except Exception:
            pass
        try:
            deal = player.metadata.get("haggle_deal", {}).get(
                merchant_npc.id, {})
            day = self.engine.world.time // (24 * 60)
            if deal.get("day") == day:
                haggle = max(haggle, deal.get("discount", 0.0))
        except Exception:
            pass

        if selling:
            return 1.0 + delta            # higher rep = higher sell price
        # rep + diary + haggle lower buy price (floor at half price)
        return max(0.5, 1.0 - delta - diary - haggle)


def merchants_near(engine, player, radius: float = 2.0):
    """Return a list of adjacent merchant NPCs (for opening a shop)."""
    from engine.presence import npc_adjacent_to_player
    out = []
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        klass = getattr(npc.character_class, "value", "")
        if klass not in ("merchant", "cleric", "wizard", "ranger"):
            continue
        if npc_adjacent_to_player(engine, npc, radius):
            out.append(npc)
    return out


