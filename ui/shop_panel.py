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
            from engine.trade_info import BULK
            bulk = bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT)
            self._transact(BULK if bulk else 1)
        elif k == pygame.K_j:   # sell all junk (PUX.2)
            self._sell_all_junk()
        elif k == pygame.K_h:   # haggle (P12.10)
            try:
                self.engine.shop_manager.haggle(
                    self.engine.player, self.merchant)
            except Exception:
                pass
        return True

    def _haggle_line(self) -> str:
        try:
            st = self.engine.shop_manager.haggle_state(
                self.engine.player, self.merchant)
            meter = "\u25cf" * st["patience"] + \
                "\u25cb" * (3 - st["patience"])
            deal = f"  deal -{int(st['discount'] * 100)}%" \
                if st["discount"] else ""
            return (f"[Enter] buy/sell  [H] haggle {meter}{deal}  "
                    f"[Esc] leave")
        except Exception:
            return "[Enter] buy/sell  [Esc] leave"

    def _move(self, delta: int) -> None:
        if self.column == 0:
            items = self._merchant_items()
            if items:
                self.cursor_left = (self.cursor_left + delta) % len(items)
        else:
            items = self._player_items()
            if items:
                self.cursor_right = (self.cursor_right + delta) % len(items)

    def _selected_item(self):
        items = self._merchant_items() if self.column == 0 \
            else self._player_items()
        cur = self.cursor_left if self.column == 0 else self.cursor_right
        return items[cur] if items and cur < len(items) else None

    def _transact(self, qty: int = 1) -> None:
        """Buy or sell up to `qty` units (PUX.2 bulk); stop early if a
        purchase can't complete (no gold / no room / merchant broke)."""
        for _ in range(max(1, qty)):
            ok = self._buy_one() if self.column == 0 else self._sell_one()
            if not ok:
                break

    def _sell_all_junk(self) -> None:
        from engine.trade_info import junk_items
        for it in junk_items(self.engine.player):
            self._sell_one(it)

    def _buy_one(self) -> bool:
        player = self.engine.player
        sm = self.engine.shop_manager
        items = self._merchant_items()
        if not items or self.cursor_left >= len(items):
            return False
        item = items[self.cursor_left]
        price = sm.buy_price(player, item, self.merchant)
        from engine.carry import can_carry, full_message
        if not can_carry(player):
            self.engine.memory_manager.add_event(full_message(player))
            return False
        if player.gold < price:
            self.engine.memory_manager.add_event(
                f"You can't afford {item.name} ({price}g).")
            return False
        player.gold -= price
        self._catalog().gold += price
        if item.stackable:
            from items.item_registry import create_item
            bought = create_item(item.id, quantity=1) or item.copy()
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
        self._train_bartering()
        return True

    def _sell_one(self, item=None) -> bool:
        player = self.engine.player
        sm = self.engine.shop_manager
        if item is None:
            items = self._player_items()
            if not items or self.cursor_right >= len(items):
                return False
            item = items[self.cursor_right]
        price = sm.sell_price(player, item, self.merchant)
        try:   # stolen goods need a fence (P12.9b)
            from engine.law import fence_sale
            ok, price, note = fence_sale(
                self.engine, item, self.merchant, price)
            if not ok:
                self.engine.memory_manager.add_event(note)
                return False
            if note:
                self.engine.memory_manager.add_event(note)
        except Exception:
            pass
        cat = self._catalog()
        if cat.gold < price:
            self.engine.memory_manager.add_event(
                f"{self.merchant.name} can't afford that right now "
                f"({cat.gold}g left). Try after they restock.")
            return False
        cat.gold -= price
        if item.stackable and item.quantity > 1:
            player.gold += price
            item.quantity -= 1
            from items.item_registry import create_item
            added = create_item(item.id, quantity=1) or item.copy()
            added.quantity = 1
            self._merchant_items().append(added)
        else:
            player.gold += price
            if item in player.inventory:
                player.inventory.remove(item)
            self._merchant_items().append(item)
            self.cursor_right = max(0, self.cursor_right - 1)
        self.engine.memory_manager.add_event(
            f"You sell {item.name} for {price}g.")
        try:
            self.engine.market.note_sale(item)   # P8.5 supply
        except Exception:
            pass
        self._train_bartering()
        return True

    def _train_bartering(self) -> None:
        """The B-key deal trains Bartering too (P15.9b)."""
        try:
            from engine.skill_progression import train_skill
            train_skill(self.engine, "bartering", 5)
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

        # Column rectangles (leave a strip at the bottom for the
        # inspect / price-breakdown pane, PUX.2)
        inspect_h = 78
        col_h = box.height - 90 - inspect_h
        col_w = (box.width - 48) // 2
        left = pygame.Rect(box.x + 16, box.y + 62, col_w, col_h)
        right = pygame.Rect(left.right + 16, box.y + 62, col_w, col_h)
        self._draw_column(target, left, "Wares", self._merchant_items(),
                          self.cursor_left,
                          is_buy=True, active=(self.column == 0))
        self._draw_column(target, right, "Your bag", self._player_items(),
                          self.cursor_right,
                          is_buy=False, active=(self.column == 1))

        inspect = pygame.Rect(box.x + 16, left.bottom + 6,
                              box.width - 32, inspect_h - 12)
        self._draw_inspect(target, inspect)

        hint = self._font.render(
            "[↔] switch  [↕] move  [Enter] deal  "
            "[Shift+Enter] x5  [J] sell junk  " + self._haggle_line(),
            True, (160, 160, 180))
        target.blit(hint, (box.x + 16, box.bottom - 22))

    def _draw_inspect(self, target, rect) -> None:
        """The selected item: what it is, how it compares to your gear,
        and WHY its price is what it is (PUX.2 transparency)."""
        pygame.draw.rect(target, (20, 20, 34), rect)
        pygame.draw.rect(target, (120, 120, 150), rect, 1)
        item = self._selected_item()
        if item is None:
            return
        from engine import trade_info
        sm = self.engine.shop_manager
        player = self.engine.player
        x, y = rect.x + 8, rect.y + 4
        for ln in trade_info.item_report(item)[:2]:
            target.blit(self._font.render(ln, True, (222, 222, 205)),
                        (x, y))
            y += 16
        cmp = trade_info.compare_to_equipped(self.engine, item)
        if cmp:
            target.blit(self._font.render(cmp, True, (150, 220, 150)),
                        (x, y))
        selling = (self.column == 1)
        price = (sm.sell_price(player, item, self.merchant) if selling
                 else sm.buy_price(player, item, self.merchant))
        factors = trade_info.price_factors(sm, player, item,
                                           self.merchant, selling)
        verb = "Sell" if selling else "Buy"
        pline = f"{verb} {price}g   ({trade_info.factors_line(factors)})"
        target.blit(self._font.render(pline, True, (240, 220, 140)),
                    (rect.right - 8 - self._font.size(pline)[0], rect.y + 4))

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
