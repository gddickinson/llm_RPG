"""Economy system — buy / sell / trade / give actions."""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("llm_rpg.economy")


class EconomySystem:
    """Handle buy/sell/trade/give between characters."""

    def __init__(self, engine):
        self.engine = engine

    # ---- public entry point used by NPC action router -----------------

    def handle(self, npc, target_text: str, action_type: str) -> bool:
        """Process an economic action by an NPC."""
        item_name, partner = self._parse_target(target_text)
        if partner:
            trader = self.engine.find_character(partner)
        else:
            trader = self._nearest_other(npc)
        if not trader:
            self._log(f"{npc.name} tries to {action_type} but no trade partner is near.")
            return False

        if not self._adjacent(npc, trader):
            return self._step_toward(npc, trader)

        if action_type == "buy":
            return self._buy(npc, trader, item_name)
        if action_type == "sell":
            return self._sell(npc, trader, item_name)
        if action_type == "give":
            return self._give(npc, trader, item_name)
        if action_type == "trade":
            return self._trade(npc, trader, item_name)
        return False

    # ---- player-facing helpers ---------------------------------------

    def player_buy(self, item_name: str, npc_name: str = None) -> str:
        partner = self._find_partner_for_player(npc_name)
        if not partner:
            return "There's no merchant nearby."
        if not self._adjacent(self.engine.player, partner):
            return f"{partner.name} is too far away."
        return self._exec_buy_player(item_name, partner)

    def player_sell(self, item_name: str, npc_name: str = None) -> str:
        partner = self._find_partner_for_player(npc_name)
        if not partner:
            return "There's no merchant nearby."
        if not self._adjacent(self.engine.player, partner):
            return f"{partner.name} is too far away."
        return self._exec_sell_player(item_name, partner)

    # ---- buy / sell core ---------------------------------------------

    def _buy(self, buyer, seller, item_name: str) -> bool:
        item = self._find_in_inventory(seller, item_name)
        if not item:
            return False
        price = self._price_of(item)
        if buyer.gold < price:
            return False
        buyer.gold -= price
        seller.gold += price
        seller.inventory.remove(item)
        buyer.inventory.append(item)
        name = item.name if hasattr(item, "name") else str(item)
        self._log(f"{buyer.name} buys {name} from {seller.name} for {price} gold.")
        return True

    def _sell(self, seller, buyer, item_name: str) -> bool:
        return self._buy(buyer, seller, item_name)

    def _give(self, giver, receiver, target_text: str) -> bool:
        # Gold gift?
        nums = re.findall(r"\d+", target_text)
        if "gold" in target_text.lower() or "coin" in target_text.lower():
            amount = int(nums[0]) if nums else 1
            if giver.gold < amount:
                return False
            giver.gold -= amount
            receiver.gold += amount
            self._log(f"{giver.name} gives {amount} gold to {receiver.name}.")
            return True

        item = self._find_in_inventory(giver, target_text)
        if not item:
            return False
        giver.inventory.remove(item)
        receiver.inventory.append(item)
        name = item.name if hasattr(item, "name") else str(item)
        self._log(f"{giver.name} gives {name} to {receiver.name}.")

        # Notify quest manager (delivery)
        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager:
            item_id = getattr(item, "id", None) or name.lower().replace(" ", "_")
            self.engine.quest_manager.on_item_delivered(item_id, receiver.id)
        return True

    def _trade(self, npc, partner, target_text: str) -> bool:
        # Simplified: try to sell first, fall back to buy
        return self._sell(npc, partner, target_text) or \
               self._buy(npc, partner, target_text)

    # ---- player buy/sell variants -------------------------------------

    def _exec_buy_player(self, item_name: str, seller) -> str:
        item = self._find_in_inventory(seller, item_name)
        if not item:
            return f"{seller.name} doesn't have any {item_name}."
        price = self._price_of(item)
        if self.engine.player.gold < price:
            return f"You can't afford the {item.name} ({price}g)."
        self.engine.player.gold -= price
        seller.gold += price
        seller.inventory.remove(item)
        self.engine.player.inventory.append(item)
        msg = f"You buy {item.name} for {price}g."
        self._log(msg)
        return msg

    def _exec_sell_player(self, item_name: str, buyer) -> str:
        item = self._find_in_inventory(self.engine.player, item_name)
        if not item:
            return f"You don't have any {item_name}."
        price = max(1, self._price_of(item) // 2)
        buyer.gold = max(0, buyer.gold - price)
        self.engine.player.gold += price
        self.engine.player.inventory.remove(item)
        buyer.inventory.append(item)
        msg = f"You sell {item.name} for {price}g."
        self._log(msg)
        return msg

    # ---- helpers ------------------------------------------------------

    def _parse_target(self, target_text: str):
        if " from " in target_text:
            i, p = target_text.split(" from ", 1)
            return i.strip(), p.strip()
        if " to " in target_text:
            i, p = target_text.split(" to ", 1)
            return i.strip(), p.strip()
        if " with " in target_text:
            i, p = target_text.split(" with ", 1)
            return i.strip(), p.strip()
        return target_text.strip(), None

    def _adjacent(self, a, b) -> bool:
        # Player pairs go through the interior-aware check (P9A.7)
        player = self.engine.player
        if a.id == player.id or b.id == player.id:
            from engine.presence import npc_adjacent_to_player
            other = b if a.id == player.id else a
            return npc_adjacent_to_player(self.engine, other)
        return ((a.position[0] - b.position[0]) ** 2 +
                (a.position[1] - b.position[1]) ** 2) ** 0.5 <= 1.5

    def _find_in_inventory(self, char, name: str):
        name = name.lower().strip()
        if not name:
            return None
        # Exact name match
        for it in char.inventory:
            it_name = it.name.lower() if hasattr(it, "name") else str(it).lower()
            if it_name == name:
                return it
        # Substring
        for it in char.inventory:
            it_name = it.name.lower() if hasattr(it, "name") else str(it).lower()
            if name in it_name or it_name in name:
                return it
        return None

    def _price_of(self, item) -> int:
        if hasattr(item, "value"):
            return max(1, int(item.value))
        return 10

    def _nearest_other(self, npc):
        nearest, best = None, 999
        for pos, ch in self.engine.world.map.characters.items():
            if ch.id == npc.id:
                continue
            d = ((pos[0] - npc.position[0]) ** 2 +
                 (pos[1] - npc.position[1]) ** 2) ** 0.5
            if d < best:
                best, nearest = d, ch
        return nearest

    def _find_partner_for_player(self, name: str = None):
        if name:
            return self.engine.find_character(name)
        for pos, ch in self.engine.world.map.characters.items():
            if ch.id == self.engine.player.id:
                continue
            if self._adjacent(self.engine.player, ch):
                return ch
        return None

    def _step_toward(self, mover, target) -> bool:
        dx = target.position[0] - mover.position[0]
        dy = target.position[1] - mover.position[1]
        dx = (dx > 0) - (dx < 0)
        dy = (dy > 0) - (dy < 0)
        if dx and dy:
            if abs(target.position[0] - mover.position[0]) > \
                    abs(target.position[1] - mover.position[1]):
                dy = 0
            else:
                dx = 0
        nx, ny = mover.position[0] + dx, mover.position[1] + dy
        return self.engine.world.map.move_character(mover, nx, ny)

    def _log(self, msg: str) -> None:
        self.engine.memory_manager.add_event(msg)
