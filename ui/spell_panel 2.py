"""Spellbook panel — cast any known spell (P5.2).

Opened with X. Lists every spell the player knows with mana cost,
effect, and range; Enter casts the highlighted spell (heals target
yourself, attacks target the nearest hostile — SpellSystem resolves).
Only 2 of the spells were reachable before this panel existed.
"""

import logging

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.spell_panel")


class SpellPanel:
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

    # ---------------- data ------------------------------------------

    def spells(self):
        try:
            return self.engine.get_player_spells()
        except Exception:
            return []

    # ---------------- input -----------------------------------------

    def handle_key(self, event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        k = event.key
        spells = self.spells()
        if k in (pygame.K_UP, pygame.K_w):
            if spells:
                self.cursor = (self.cursor - 1) % len(spells)
        elif k in (pygame.K_DOWN, pygame.K_s):
            if spells:
                self.cursor = (self.cursor + 1) % len(spells)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self._cast_selected(spells)
        elif pygame.K_1 <= k <= pygame.K_9:
            idx = k - pygame.K_1
            if (getattr(event, "mod", 0) & pygame.KMOD_SHIFT) and idx < 5 \
                    and self.cursor < len(spells):
                # SHIFT+N binds the highlighted spell to quick-slot N (P22.6)
                from engine.quick_spells import set_slot
                sp = spells[self.cursor]
                set_slot(self.engine.player, idx, sp.id)
                self.engine.memory_manager.add_event(
                    f"[Cast] {sp.name} bound to quick-slot {idx + 1}.")
            elif idx < len(spells):
                self.cursor = idx
                self._cast_selected(spells)
        return True

    def _cast_selected(self, spells) -> None:
        if not spells or self.cursor >= len(spells):
            return
        spell = spells[self.cursor]
        target = "me" if (spell.heal and not spell.damage) else None
        try:
            msg = self.engine.cast_spell(spell.id, target)
            self.engine.memory_manager.add_event(msg)
        except Exception as e:
            logger.debug(f"cast failed: {e}")

    # ---------------- render ----------------------------------------

    def draw(self, target, screen_rect) -> None:
        if not PYGAME_OK:
            return
        self._ensure_font()
        # George: a compact RIGHT-SIDE RAIL, not a centred box, so the
        # battlefield stays fully visible while you pick a spell
        w = min(340, max(240, screen_rect.width // 3))
        h = screen_rect.height - 60
        box = pygame.Rect(screen_rect.right - w - 12, 30, w, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((12, 10, 26, 224))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (140, 120, 220), box, 2)

        mana, max_mana = self.engine.get_player_mana()
        title = self._big.render("Spellbook", True, (190, 170, 255))
        target.blit(title, (box.x + 12, box.y + 8))
        mana_txt = self._font.render(
            f"Mana: {mana}/{max_mana}", True, (150, 170, 240))
        target.blit(mana_txt, (box.x + 12, box.y + 34))

        spells = self.spells()
        if self.cursor >= len(spells):
            self.cursor = max(0, len(spells) - 1)
        if not spells:
            none = self._font.render(
                "You know no spells.", True, (170, 170, 190))
            target.blit(none, (box.x + 12, box.y + 64))

        line_h = 34
        y = box.y + 58
        for idx, spell in enumerate(spells[:12]):
            selected = idx == self.cursor
            affordable = mana >= spell.mana_cost
            color = ((255, 240, 170) if selected else (225, 225, 235)) \
                if affordable else \
                ((180, 150, 150) if selected else (130, 125, 140))
            prefix = f"> {idx + 1}. " if selected else f"  {idx + 1}. "
            head = f"{prefix}{spell.name} ({spell.mana_cost}m)"
            target.blit(self._font.render(head, True, color),
                        (box.x + 12, y))
            effect = []
            if spell.damage:
                effect.append(f"dmg {spell.damage}")
            if spell.heal:
                effect.append(f"heal {spell.heal}")
            if spell.status_effect:
                effect.append(spell.status_effect)
            sub = f"     rng {int(spell.range)} · " + " · ".join(effect)
            target.blit(self._font.render(sub[:42], True, (150, 150, 170)),
                        (box.x + 12, y + 15))
            y += line_h

        for i, ln in enumerate(("[1-9] cast · SHIFT+N favourite",
                                "[Enter] cast sel · [Esc] close")):
            hint = self._font.render(ln, True, (160, 160, 180))
            target.blit(hint, (box.x + 12, box.bottom - 40 + i * 18))
