"""Shop panel — interactive buy/sell interface.

Two columns: merchant wares (left) | player inventory (right).
Up/Down moves cursor; Left/Right switches columns.
Enter buys (left) or sells (right). Esc closes.
"""

import logging
from typing import List, Optional

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.shop_panel")


class ShopPanel:
    """Stateful shop overlay; held by the GUI in 'shop' mode."""

    def __init__(self, engine, merchant_npc):
        self.engine = engine
        self.merchant = merchant_npc
        self.column = 0          # 0 = merchant wares, 1 = player inventory
        self.cursor_left = 0
        self.cursor_right = 0
        self.scroll_left = 0
        self.scroll_right = 0
        self._font = None
        self._big = None

    def _ensure_font(self):
        if self._font is None and PYGAME_OK:
            pygame.font.init()
            self._font = pygame.font.SysFont("monospace", 14)
            self._big = pygame.font.SysFont("monospace", 18, bold=True)

    # ---------------- data ------------------------------------------

    def _catalog(self):
        return self.engine.shop_manager.catalog_for(self.merchant)

    def _merchant_items(self):
        return self._catalog().items

    def _player_items(self):
        return list(self.engine.player.inventory)

    # ---------------- input -----------------------------------------

    def handle_key(self, event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        k = event.key
        if k in (pygame.K_LEFT, pygame.K_a):
            self.column = 0
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.column = 1
        elif k in (pygame.K_UP, pygame.K_w):
            self._move(-1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self._move(1)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self._transact()
        return True

    def _move(self, delta: int) -> None:
        if self.column == 0:
            items = self._merchant_items()
            if items:
                self.cursor_left = (self.cursor_left + delta) % len(items)
        else:
            items = self._player_items()
            if items:
                self.cursor_right = (self.cursor_right + delta) % len(items)

    def _transact(self) -> None:
        player = self.engine.player
        sm = self.engine.shop_manager
        if self.column == 0:
            items = self._merchant_items()
            if not items or self.cursor_left >= len(items):
                return
            item = items[self.cursor_left]
            price = sm.buy_price(player, item, self.merchant)
            from engine.carry import can_carry, full_message
            if not can_carry(player):
                self.engine.memory_manager.add_event(
                    full_message(player))
                return
            if player.gold < price:
                self.engine.memory_manager.add_event(
                    f"You can't afford {item.name} ({price}g).")
                return
            # Pay; reduce stack if stackable, else remove
            player.gold -= price
            self._catalog().gold += price
            if item.stackable:
                # Take a single unit from the stack
                from items.item_registry import create_item
                bought = create_item(item.id, quantity=1)
                if bought is None:
                    bought = item.copy()
                    bought.quantity = 1
                player.inventory.append(bought)
                item.quantity -= 1
                if item.quantity <= 0:
                    items.pop(self.cursor_left)
                    self.cursor_left = max(0, self.cursor_left - 1)
            else:
                player.inventory.append(item)
                items.pop(self.cursor_left)
                self.cursor_left = max(0, self.cursor_left - 1)
            self.engine.memory_manager.add_event(
                f"You buy {item.name} for {price}g.")
            try:
                self.engine.market.note_purchase(item)   # P8.5 demand
            except Exception:
                pass
        else:
            items = self._player_items()
            if not items or self.cursor_right >= len(items):
                return
            item = items[self.cursor_right]
            price = sm.sell_price(player, item, self.merchant)
            try:   # stolen goods need a fence (P12.9b)
                from engine.law import fence_sale
                ok, price, note = fence_sale(
                    self.engine, item, self.merchant, price)
                if not ok:
                    self.engine.memory_manager.add_event(note)
                    return
                if note:
                    self.engine.memory_manager.add_event(note)
            except Exception:
                pass
            cat = self._catalog()
            if cat.gold < price:
                self.engine.memory_manager.add_event(
                    f"{self.merchant.name} can't afford that right now "
                    f"({cat.gold}g left). Try after they restock.")
                return
            cat.gold -= price
            # Transfer one unit
            if item.stackable and item.quantity > 1:
                player.gold += price
                item.quantity -= 1
                from items.item_registry import create_item
                added = create_item(item.id, quantity=1) or item.copy()
                added.quantity = 1
                self._merchant_items().append(added)
            else:
                player.gold += price
                player.inventory.remove(item)
                self._merchant_items().append(item)
                self.cursor_right = max(0, self.cursor_right - 1)
            self.engine.memory_manager.add_event(
                f"You sell {item.name} for {price}g.")
            try:
                self.engine.market.note_sale(item)   # P8.5 supply
            except Exception:
                pass

    # ---------------- render ----------------------------------------

    def draw(self, target, screen_rect) -> None:
        if not PYGAME_OK:
            return
        self._ensure_font()
        w = min(screen_rect.width - 60, 760)
        h = min(screen_rect.height - 80, 500)
        box = pygame.Rect((screen_rect.width - w) // 2,
                          (screen_rect.height - h) // 2, w, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 235))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (200, 180, 100), box, 2)

        title = self._big.render(
            f"Shop — {self.merchant.name}", True, (255, 220, 120))
        target.blit(title, (box.x + 16, box.y + 10))

        # Stats line
        try:
            from engine.effects import effective_ac
            ac = effective_ac(self.engine.player)
        except Exception:
            ac = 10
        stats = self._font.render(
            f"Gold: {self.engine.player.gold}    AC: {ac}    "
            f"{self.merchant.name}'s purse: {self._catalog().gold}g",
            True, (200, 200, 220))
        target.blit(stats, (box.x + 16, box.y + 36))

        # Column rectangles
        col_h = box.height - 90
        col_w = (box.width - 48) // 2
        left = pygame.Rect(box.x + 16, box.y + 62, col_w, col_h)
        right = pygame.Rect(left.right + 16, box.y + 62, col_w, col_h)
        self._draw_column(target, left, "Wares", self._merchant_items(),
                          self.cursor_left,
                          is_buy=True, active=(self.column == 0))
        self._draw_column(target, right, "Your bag", self._player_items(),
                          self.cursor_right,
                          is_buy=False, active=(self.column == 1))

        hint = self._font.render(
            "[Left/Right] switch  [Up/Down] move  "
            "[Enter] buy/sell  [Esc] leave",
            True, (160, 160, 180))
        target.blit(hint, (box.x + 16, box.bottom - 24))

    def _draw_column(self, target, rect, label, items, cursor,
                     is_buy: bool, active: bool) -> None:
        # Header
        head_color = (255, 220, 120) if active else (180, 180, 200)
        pygame.draw.rect(target, (40, 40, 60) if active else (25, 25, 40),
                         rect)
        pygame.draw.rect(target, head_color, rect, 1)
        h_label = self._font.render(label, True, head_color)
        target.blit(h_label, (rect.x + 8, rect.y + 4))

        line_h = 18
        max_rows = (rect.height - 28) // line_h
        # Auto-scroll
        scroll = 0
        if cursor >= max_rows:
            scroll = cursor - max_rows + 1
        y = rect.y + 26
        sm = self.engine.shop_manager
        for idx in range(scroll, min(len(items), scroll + max_rows)):
            it = items[idx]
            if is_buy:
                price = sm.buy_price(self.engine.player, it, self.merchant)
            else:
                price = sm.sell_price(self.engine.player, it, self.merchant)
            prefix = "> " if (active and idx == cursor) else "  "
            color = (255, 240, 160) if (active and idx == cursor) \
                else (220, 220, 220)
            qty = f" x{it.quantity}" if it.stackable and it.quantity > 1 else ""
            text = f"{prefix}{it.name}{qty}  {price}g"
            txt = self._font.render(text, True, color)
            target.blit(txt, (rect.x + 8, y))
            y += line_h
