"""Interactive inventory panel.

Shown when the player presses I. Displays the 6 equipment slots followed
by the inventory bag. Cursor navigates with up/down. Hotkeys:
    E - equip / unequip the highlighted item
    Q - quaff / use the highlighted item
    D - drop the highlighted item
    Esc - close
"""

import logging
from typing import List, Optional

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.inventory_panel")


_SLOT_LABELS = [
    ("Weapon", "weapon"),
    ("Armor", "armor"),
    ("Shield", "shield"),
    ("Amulet", "amulet"),
    ("Ring", "ring"),
    ("Boots", "boots"),
]


class InventoryPanel:
    """Stateful overlay for browsing + manipulating the inventory."""

    def __init__(self, engine):
        self.engine = engine
        self.cursor = 0       # index into the combined rows
        self.scroll = 0
        self._font = None
        self._big = None

    def _ensure_font(self):
        if self._font is None and PYGAME_OK:
            pygame.font.init()
            self._font = pygame.font.SysFont("monospace", 14)
            self._big = pygame.font.SysFont("monospace", 18, bold=True)

    # ---------------- data model -----------------------------------

    def rows(self):
        """Return ordered list of rows: (kind, label, item_or_None, slot_key)."""
        out = []
        try:
            from characters.equipment import get_equipment
            eq = get_equipment(self.engine.player)
        except Exception:
            eq = {k: None for _, k in _SLOT_LABELS}
        for label, slot in _SLOT_LABELS:
            out.append(("equip", label, eq.get(slot), slot))
        out.append(("sep", "-- Inventory --", None, None))
        for it in self.engine.player.inventory:
            out.append(("bag", "", it, None))
        # Home chest (P15.7) — show stored goods so they're never invisible or
        # unrecoverable; [H] on a chest row takes the item back
        try:
            from engine.homestead import is_ready, _storage
            from items.item import Item
            if is_ready(self.engine.player):
                stored = _storage(self.engine.player)
                if stored:
                    out.append(("sep", "-- Home Chest ([H] take back) --",
                                None, None))
                    for d in stored:
                        out.append(("chest", "", Item.from_dict(d), None))
        except Exception:
            pass
        return out

    # ---------------- input ----------------------------------------

    def handle_key(self, event) -> bool:
        """Return True if consumed."""
        if event.type != pygame.KEYDOWN:
            return False
        k = event.key
        rows = self.rows()
        if k in (pygame.K_UP, pygame.K_w):
            self._move_cursor(-1, rows)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self._move_cursor(1, rows)
        elif k == pygame.K_e:
            self._equip_unequip(rows)
        elif k == pygame.K_q:
            self._use(rows)
        elif k == pygame.K_d:
            self._drop(rows)
        elif k == pygame.K_t:
            self._transmute(rows)
        elif k == pygame.K_h:
            self._store(rows)
        return True

    def _move_cursor(self, delta: int, rows) -> None:
        n = len(rows)
        if n == 0:
            return
        c = self.cursor
        for _ in range(n):
            c = (c + delta) % n
            if rows[c][0] != "sep":
                self.cursor = c
                return

    def _row_at_cursor(self, rows):
        if 0 <= self.cursor < len(rows):
            return rows[self.cursor]
        return None

    def _equip_unequip(self, rows) -> None:
        row = self._row_at_cursor(rows)
        if row is None:
            return
        kind, label, item, slot = row
        from characters.equipment import equip, unequip, EquipSlot, slot_for_item
        if kind == "equip" and item is not None:
            # Unequip
            try:
                unequip(self.engine.player, EquipSlot(slot))
            except Exception:
                pass
        elif kind == "bag" and item is not None:
            if not hasattr(item, "is_equippable"):
                self.engine.memory_manager.add_event(
                    f"You can't equip {item}.")
                return
            if not item.is_equippable():
                self.engine.memory_manager.add_event(
                    f"{item.name} can't be equipped.")
                return
            equip(self.engine.player, item)

    def _use(self, rows) -> None:
        row = self._row_at_cursor(rows)
        if row is None:
            return
        kind, _, item, _ = row
        if item is None or kind == "equip":
            return
        if not hasattr(item, "name"):
            return
        # Use via the engine API for consistent messaging
        self.engine.use_item(item.name)

    def _drop(self, rows) -> None:
        row = self._row_at_cursor(rows)
        if row is None:
            return
        kind, _, item, _ = row
        if item is None or kind != "bag":
            return
        self.engine.drop_item(item.name if hasattr(item, "name")
                              else str(item))

    def _transmute(self, rows) -> None:
        """P13.1: the value floor — coin from any carried thing."""
        row = self._row_at_cursor(rows)
        if row is None:
            return
        kind, _, item, _ = row
        if item is None or kind != "bag" or not hasattr(item, "id"):
            return
        from engine.item_use import transmute_item
        transmute_item(self.engine, item)

    def _store(self, rows) -> None:
        """P15.7: [H] moves an item between the pack and the home chest — DEPOSIT
        a highlighted bag item, or WITHDRAW (take back) a highlighted chest item
        (so stashed goods are never lost)."""
        row = self._row_at_cursor(rows)
        if row is None:
            return
        kind, _, item, _ = row
        if item is None:
            return
        name = item.name if hasattr(item, "name") else str(item)
        if kind == "bag":
            msg = self.engine.home_deposit(name)
        elif kind == "chest":
            msg = self.engine.home_withdraw(name)
        else:
            return
        if msg:
            self.engine.memory_manager.add_event(msg)

    # ---------------- render ---------------------------------------

    def draw(self, target, screen_rect) -> None:
        if not PYGAME_OK:
            return
        self._ensure_font()

        w = min(screen_rect.width - 80, 560)
        h = min(screen_rect.height - 80, 480)
        box = pygame.Rect((screen_rect.width - w) // 2,
                          (screen_rect.height - h) // 2, w, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 235))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (200, 180, 100), box, 2)

        title = self._big.render("Inventory", True, (255, 220, 120))
        target.blit(title, (box.x + 16, box.y + 10))

        # Stat header — gold, HP, effective AC, etc.
        try:
            from engine.effects import (
                effective_ac, effective_stat, effective_max_hp,
                effective_max_mana,
            )
            p = self.engine.player
            ac = effective_ac(p)
            stats_line = (
                f"Gold {p.gold}    HP {p.hp}/{effective_max_hp(p)}    "
                f"AC {ac}    "
                f"STR {effective_stat(p, 'strength')}  "
                f"DEX {effective_stat(p, 'dexterity')}  "
                f"CON {effective_stat(p, 'constitution')}"
            )
            mana = (p.metadata or {}).get("mana", 0)
            max_mana = effective_max_mana(p)
            if max_mana > 0:
                stats_line += f"    Mana {mana}/{max_mana}"
            text = self._font.render(stats_line, True, (200, 200, 220))
            target.blit(text, (box.x + 16, box.y + 38))
        except Exception:
            pass

        rows = self.rows()
        y = box.y + 64
        line_h = 18
        max_rows = (box.height - 100) // line_h

        # Adjust scroll to keep cursor visible
        if self.cursor < self.scroll:
            self.scroll = self.cursor
        if self.cursor >= self.scroll + max_rows:
            self.scroll = self.cursor - max_rows + 1

        for idx in range(self.scroll, min(len(rows), self.scroll + max_rows)):
            kind, label, item, slot = rows[idx]
            color = (220, 220, 220)
            prefix = "  "
            if idx == self.cursor and kind != "sep":
                prefix = "> "
                color = (255, 240, 120)
            line = self._render_row(kind, label, item, prefix)
            txt = self._font.render(line, True, color)
            target.blit(txt, (box.x + 16, y))
            y += line_h

        status = self._font.render(self._status_line(),
                                   True, (200, 200, 150))
        target.blit(status, (box.x + 16, box.bottom - 48))
        hint = self._font.render(
            "[Up/Down] move  [E] (un)equip  [Q] use  [D] drop  "
            "[T] transmute  [H] store  [Esc] close",
            True, (160, 160, 180))
        target.blit(hint, (box.x + 16, box.bottom - 28))

    def _status_line(self) -> str:
        p = self.engine.player
        parts = []
        try:
            from engine.effects import effective_ac
            parts.append(f"AC {effective_ac(p)}")
        except Exception:
            pass
        try:
            from characters.equipment import set_bonus
            n, name = set_bonus(p)
            if n:
                parts.append(f"{name} set +{n} AC ({n} pcs)")
        except Exception:
            pass
        try:
            from engine.carry import capacity, used_slots
            parts.append(f"pack {used_slots(p)}/{capacity(p)}")
        except Exception:
            pass
        return "   ".join(parts)

    def _render_row(self, kind, label, item, prefix) -> str:
        if kind == "sep":
            return f"  {label}"
        if kind == "equip":
            iname = item.name if item is not None else "(empty)"
            if item is not None:
                try:
                    from engine.durability import durability_label
                    iname += durability_label(item)
                except Exception:
                    pass
            return f"{prefix}[{label:7s}] {iname}"
        # bag — tolerate plain strings (picked-up body markers);
        # George hit a hard crash here
        if not hasattr(item, "name"):
            return f"{prefix}{str(item)}"
        name = item.name
        qty = f" x{item.quantity}" if item.stackable and item.quantity > 1 else ""
        suffix = ""
        if item.is_weapon():
            kind_label = item.weapon_kind or "melee"
            suffix = f"  ({kind_label} dmg {item.damage})"
        elif item.is_armor():
            suffix = f"  (armor {item.armor})"
        elif item.is_ammo():
            suffix = f"  (ammo {item.ammo_type})"
        return f"{prefix}{name}{qty}{suffix}"
