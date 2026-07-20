"""Interactive crafting panel.

Shown when the player presses K. Lists every recipe with live
have/need ingredient counts and gold cost; recipes you can't craft
here (missing ingredients, not enough gold, or not at the required
station such as a forge) are greyed out with the reason shown.

    Up/Down - move cursor
    Enter   - craft the highlighted recipe
    Esc / K - close
"""

import logging

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.crafting_panel")


class CraftingPanel:
    """Stateful overlay for browsing + executing crafting recipes."""

    def __init__(self, engine):
        self.engine = engine
        self.cursor = 0
        self._font = None
        self._big = None

    def _ensure_font(self):
        if self._font is None and PYGAME_OK:
            pygame.font.init()
            self._font = pygame.font.SysFont("monospace", 14)
            self._big = pygame.font.SysFont("monospace", 18, bold=True)

    # ---------------- data model -----------------------------------

    def _location_props(self) -> dict:
        loc = self.engine.world.get_location_at(
            *self.engine.player.position)
        return dict(loc.properties) if loc else {}

    def rows(self):
        """Ordered list of (recipe, reason) — reason == '' if craftable."""
        from items.crafting import list_recipes, can_craft
        props = self._location_props()
        player = self.engine.player
        out = []
        for recipe in list_recipes():
            reason = can_craft(player, recipe.output_id, props)
            out.append((recipe, reason))
        # Craftable first, then alphabetical by output name
        out.sort(key=lambda pair: (bool(pair[1]), pair[0].output_name()))
        return out

    def repair_rows(self):
        """(item, cost) for damaged equipped gear — only at a forge."""
        if not self._location_props().get("forge"):
            return []
        from engine.durability import damaged_equipped_items, repair_cost
        return [(it, repair_cost(it))
                for it in damaged_equipped_items(self.engine.player)]

    def enchant_rows(self):
        """(item, eid, ench, reason) — M3 enchantments applicable to WORN gear."""
        from items import enchanting as en
        from characters.equipment import equipped_items
        out = []
        for item in equipped_items(self.engine.player):
            for eid in en.all_applicable(item):
                ok, why = en.can_enchant(self.engine, item, eid)
                out.append((item, eid, en.enchantment(eid), "" if ok else why))
        return out

    # ---------------- input -----------------------------------------

    def handle_key(self, event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        k = event.key
        total = (len(self.rows()) + len(self.repair_rows())
                 + len(self.enchant_rows()))
        if k in (pygame.K_UP, pygame.K_w):
            if total:
                self.cursor = (self.cursor - 1) % total
        elif k in (pygame.K_DOWN, pygame.K_s):
            if total:
                self.cursor = (self.cursor + 1) % total
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate_selected()
        return True

    def _activate_selected(self) -> None:
        rows = self.rows()
        repairs = self.repair_rows()
        enchants = self.enchant_rows()
        if self.cursor < len(rows):
            recipe, _ = rows[self.cursor]
            # engine.craft re-validates and logs the outcome either way
            self.engine.craft(recipe.output_id)
        elif self.cursor < len(rows) + len(repairs):
            from engine.durability import repair
            item, _ = repairs[self.cursor - len(rows)]
            msg = repair(self.engine.player, item, at_forge=True)
            self.engine.memory_manager.add_event(msg)
        else:
            i = self.cursor - len(rows) - len(repairs)
            if 0 <= i < len(enchants):
                from items import enchanting as en
                item, eid, _e, _r = enchants[i]
                ok, msg = en.enchant(self.engine, item, eid)
                self.engine.memory_manager.add_event(msg)

    # ---------------- render ----------------------------------------

    def _ingredient_line(self, recipe) -> str:
        from items.crafting import _count_in_inventory
        from items.item_registry import ITEM_REGISTRY
        parts = []
        for iid, qty in recipe.ingredients.items():
            item = ITEM_REGISTRY.get(iid)
            name = item.name if item else iid
            have = _count_in_inventory(self.engine.player, iid)
            parts.append(f"{min(have, qty)}/{qty} {name}")
        if recipe.gold_cost:
            parts.append(f"{recipe.gold_cost}g")
        return ", ".join(parts) if parts else "free"

    def draw(self, target, screen_rect) -> None:
        if not PYGAME_OK:
            return
        self._ensure_font()
        w = min(screen_rect.width - 60, 700)
        h = min(screen_rect.height - 80, 460)
        box = pygame.Rect((screen_rect.width - w) // 2,
                          (screen_rect.height - h) // 2, w, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 235))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (200, 180, 100), box, 2)

        at_forge = bool(self._location_props().get("forge"))
        title = self._big.render(
            "Crafting" + ("  (at forge)" if at_forge else ""),
            True, (255, 220, 120))
        target.blit(title, (box.x + 16, box.y + 10))
        gold = self._font.render(
            f"Gold: {self.engine.player.gold}", True, (200, 200, 220))
        target.blit(gold, (box.x + 16, box.y + 36))

        rows = self.rows()
        repairs = self.repair_rows()
        entries = []
        for recipe, reason in rows:
            craftable = not reason
            detail = self._ingredient_line(recipe) if craftable else reason
            entries.append((recipe.output_name(), detail, craftable))
        for item, cost in repairs:
            from engine.durability import durability_label
            entries.append((f"Repair {item.name}{durability_label(item)}",
                            f"{cost}g at the forge", True))
        for item, eid, ench, reason in self.enchant_rows():
            ok = not reason
            reagents = ", ".join(f"{q}x {r.replace('_', ' ')}"
                                 for r, q in (ench.get("reagents") or {}).items())
            entries.append((f"Enchant {item.name} — {ench['name']}",
                            reagents if ok else reason, ok))
        if self.cursor >= len(entries):
            self.cursor = max(0, len(entries) - 1)

        line_h = 34
        max_rows = (box.height - 110) // line_h
        scroll = 0
        if self.cursor >= max_rows:
            scroll = self.cursor - max_rows + 1
        y = box.y + 62
        for idx in range(scroll, min(len(entries), scroll + max_rows)):
            name, detail, ok = entries[idx]
            selected = idx == self.cursor
            name_color = ((255, 240, 160) if selected else (220, 220, 220)) \
                if ok else \
                ((200, 170, 140) if selected else (130, 130, 145))
            prefix = "> " if selected else "  "
            txt = self._font.render(f"{prefix}{name}", True, name_color)
            target.blit(txt, (box.x + 16, y))
            det_color = (150, 200, 150) if ok else (170, 130, 130)
            det = self._font.render("    " + detail, True, det_color)
            target.blit(det, (box.x + 16, y + 15))
            y += line_h

        hint = self._font.render(
            "[Up/Down] move  [Enter] craft  [Esc] close",
            True, (160, 160, 180))
        target.blit(hint, (box.x + 16, box.bottom - 24))
