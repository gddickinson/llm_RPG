"""P22.6 — the non-blocking quick-cast HUD bar.

A compact row of numbered spell slots (1-5) with mana-ready shading, drawn over
the top-left of the map so the battlefield stays fully visible while you cast.
Reads `engine.quick_spells`; shown only for a caster who has favourited spells,
so it never clutters a non-caster's screen.
"""

import pygame

BOX = 46
GAP = 4
PAD = 4


def draw_quickbar(target, engine, map_rect, font) -> None:
    if font is None:
        return
    from engine.quick_spells import get_slots, ensure_defaults, MAX_SLOTS
    from engine.spells import SPELL_REGISTRY, get_mana
    player = engine.player
    ensure_defaults(player)
    slots = get_slots(player)
    if not any(slots):
        return

    mana = get_mana(player)[0]
    n = min(MAX_SLOTS, len(slots))
    total_w = n * BOX + (n - 1) * GAP + PAD * 2
    x0 = map_rect.x + 8
    y0 = map_rect.y + 8

    bg = pygame.Surface((total_w, BOX + PAD * 2), pygame.SRCALPHA)
    bg.fill((10, 10, 22, 190))
    target.blit(bg, (x0, y0))

    for i in range(n):
        bx = x0 + PAD + i * (BOX + GAP)
        by = y0 + PAD
        sid = slots[i] if i < len(slots) else None
        spell = SPELL_REGISTRY.get(sid) if sid else None
        ready = spell is not None and mana >= spell.mana_cost
        border = (150, 130, 230) if ready else (70, 66, 90)
        pygame.draw.rect(target, (24, 20, 40), (bx, by, BOX, BOX))
        pygame.draw.rect(target, border, (bx, by, BOX, BOX), 2)
        target.blit(font.render(str(i + 1), True, (200, 190, 240)),
                    (bx + 3, by + 2))
        if spell is None:
            continue
        col = (230, 224, 255) if ready else (120, 116, 140)
        label = font.render(spell.name[:6], True, col)
        target.blit(label, (bx + BOX // 2 - label.get_width() // 2,
                            by + BOX // 2 - label.get_height() // 2))
        cost = font.render(str(spell.mana_cost), True,
                           (120, 180, 255) if ready else (90, 90, 120))
        target.blit(cost, (bx + BOX - cost.get_width() - 3,
                           by + BOX - cost.get_height() - 2))
