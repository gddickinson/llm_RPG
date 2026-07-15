"""Market prices (P8.5) — tâtonnement, ported from autonomous_world.

Prices discover themselves instead of being constants: every player
purchase nudges that category's price index up, every sale nudges it
down, and each night the index takes one sticky tâtonnement step and
then decays gently toward parity — so a shopping spree makes swords
dear for a few days, flooding the market with pelts cheapens them,
and a quiet week drifts everything back to book value. Village stores
from the faction ticker add a supply-side signal (full granaries ease
consumable prices; hungry ones raise them). Notable moves are
announced through the rumor mill.

The index multiplies BOTH buy and sell prices, so margins are
preserved and there is no buy-low-sell-high perpetual-motion machine.
Clamped to [0.6, 1.6]; the director's targeted shortages stack on
top. State persists via save_load. Pure code and arithmetic — no LLM.
"""

import logging
import math
from typing import Dict

logger = logging.getLogger("llm_rpg.market")

RATE = 0.08              # tâtonnement step size
DECAY = 0.10             # nightly drift back toward 1.0
CLAMP_LO, CLAMP_HI = 0.6, 1.6
NOTE_AT = 1.25           # rumor when an index crosses this (or 1/this)
STORES_HIGH, STORES_LOW = 70, 30

# item_type -> market category
CATEGORY = {
    "weapon": "arms", "armor": "arms", "shield": "arms",
    "ammo": "arms",
    "consumable": "provisions", "ingredient": "provisions",
    "misc": "goods", "book": "goods", "key": "goods",
    "scroll": "arcana", "amulet": "arcana", "ring": "arcana",
    "boots": "arms",
}
CATEGORIES = ("arms", "provisions", "goods", "arcana")


def category_of(item) -> str:
    t = getattr(item, "item_type", "misc")
    t = getattr(t, "value", t) or "misc"
    return CATEGORY.get(t, "goods")


class MarketSystem:
    def __init__(self, engine):
        self.engine = engine
        self.index: Dict[str, float] = {c: 1.0 for c in CATEGORIES}
        self._net: Dict[str, int] = {c: 0 for c in CATEGORIES}

    # -------------------------------------------------------- signals

    def note_purchase(self, item) -> None:
        """Player bought: demand."""
        self._net[category_of(item)] = \
            self._net.get(category_of(item), 0) + 1

    def note_sale(self, item) -> None:
        """Player sold: supply."""
        self._net[category_of(item)] = \
            self._net.get(category_of(item), 0) - 1

    def multiplier(self, item) -> float:
        return self.index.get(category_of(item), 1.0)

    # -------------------------------------------------------- nightly

    def run_day(self) -> None:
        try:
            stores = self.engine.faction_ticker.state["villagers"][
                "stores"]
            if stores >= STORES_HIGH:
                self._net["provisions"] -= 2
            elif stores <= STORES_LOW:
                self._net["provisions"] += 2
        except Exception:
            pass
        for cat in CATEGORIES:
            old = self.index.get(cat, 1.0)
            excess = self._net.get(cat, 0)
            new = old * (1.0 + RATE * math.tanh(excess / 3.0))
            new += (1.0 - new) * DECAY          # sticky drift home
            new = max(CLAMP_LO, min(CLAMP_HI, new))
            self.index[cat] = new
            self._net[cat] = 0
            self._maybe_announce(cat, old, new)

    def _maybe_announce(self, cat: str, old: float, new: float) -> None:
        crossed_up = old < NOTE_AT <= new
        crossed_down = old > (1 / NOTE_AT) >= new
        if not (crossed_up or crossed_down):
            return
        note = (f"Prices for {cat} {'climb' if crossed_up else 'tumble'}"
                f" at the market.")
        self.engine.memory_manager.add_event(f"[Realm] {note}")
        try:
            self.engine.world_director.rumors.append(note)
            del self.engine.world_director.rumors[:-5]
        except Exception:
            pass

    # ---------------------------------------------------- persistence

    def to_dict(self) -> dict:
        return {"index": dict(self.index), "net": dict(self._net)}

    def from_dict(self, data: dict) -> None:
        self.index = {c: float(data.get("index", {}).get(c, 1.0))
                      for c in CATEGORIES}
        self._net = {c: int(data.get("net", {}).get(c, 0))
                     for c in CATEGORIES}
