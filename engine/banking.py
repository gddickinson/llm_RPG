"""Banking — deposit/withdraw gold at certain locations.

The player can deposit gold at any location with property `type == 'temple'`
or `type == 'shop'`. Bank balance is stored in `player.metadata['bank']`.

Banked gold survives death (currently not implemented — but a foundation
for that).
"""

import logging
from typing import Tuple

logger = logging.getLogger("llm_rpg.banking")


# Locations that accept deposits
BANK_LOCATION_TYPES = ("temple", "shop")


class Bank:
    """Banking operations on the player."""

    def __init__(self, engine):
        self.engine = engine

    def is_at_bank(self) -> Tuple[bool, str]:
        """Return (allowed, location_name) for player's current position."""
        try:
            loc = self.engine.player_location()   # interior-aware (P9A.6)
        except Exception:
            loc = self.engine.world.get_location_at(
                *self.engine.player.position)
        if not loc:
            return (False, "")
        ltype = loc.get_property("type", "")
        # Default: temples are always banks; shops also act as small vaults
        if (ltype in BANK_LOCATION_TYPES
                or "temple" in loc.name.lower()
                or "shop" in loc.name.lower()
                or "store" in loc.name.lower()):
            return (True, loc.name)
        return (False, loc.name)

    def balance(self) -> int:
        meta = getattr(self.engine.player, "metadata", None) or {}
        return meta.get("bank", 0)

    def deposit(self, amount: int) -> str:
        ok, name = self.is_at_bank()
        if not ok:
            return "You can only deposit gold at a temple or shop."
        if amount <= 0:
            return "Specify a positive amount."
        if self.engine.player.gold < amount:
            return f"You only have {self.engine.player.gold} gold."
        self.engine.player.gold -= amount
        meta = getattr(self.engine.player, "metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}
            self.engine.player.metadata = meta
        meta["bank"] = meta.get("bank", 0) + amount
        msg = f"You deposit {amount}g at the {name}. (Balance: {meta['bank']}g)"
        self.engine.memory_manager.add_event(msg)
        return msg

    def withdraw(self, amount: int) -> str:
        ok, name = self.is_at_bank()
        if not ok:
            return "You can only withdraw gold at a temple or shop."
        if amount <= 0:
            return "Specify a positive amount."
        meta = getattr(self.engine.player, "metadata", None) or {}
        bal = meta.get("bank", 0)
        if bal < amount:
            return f"Your bank balance is only {bal}g."
        meta["bank"] = bal - amount
        self.engine.player.gold += amount
        msg = f"You withdraw {amount}g from the {name}. (Balance: {meta['bank']}g)"
        self.engine.memory_manager.add_event(msg)
        return msg

    def deposit_all(self) -> str:
        return self.deposit(self.engine.player.gold)

    def withdraw_all(self) -> str:
        meta = getattr(self.engine.player, "metadata", None) or {}
        bal = meta.get("bank", 0)
        return self.withdraw(bal) if bal > 0 else "Your bank balance is empty."
