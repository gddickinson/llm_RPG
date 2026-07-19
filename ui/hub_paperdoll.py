"""The Equipment tab of the Character Hub (GAP.6): a paper-doll mannequin
with the six worn slots, the bag grid, and DRAG-AND-DROP between them
(drag a bag item onto a slot to equip, a slot to the bag to unequip; a
plain click does the same as a shortcut).

The geometry + drop logic are pure and headless-testable; only `draw`
touches pygame.
"""

try:
    import pygame
    PYGAME_OK = True
except ImportError:                       # pragma: no cover
    PYGAME_OK = False

from characters import equipment as eqp

# slot draw order + a friendly label; positions are computed around the doll
SLOTS = ["amulet", "weapon", "armor", "shield", "ring", "boots"]
SLOT_LABEL = {"weapon": "Weapon", "armor": "Armour", "shield": "Shield",
              "amulet": "Amulet", "ring": "Ring", "boots": "Boots"}
SLOT_SIZE = 54
BAG_COLS = 6
CELL = 48
CELL_PAD = 6


# ---- geometry (pure) --------------------------------------------------

def _doll_rect(rect):
    """The left region that holds the mannequin + slots."""
    from pygame import Rect
    w = int(rect.width * 0.46)
    return Rect(rect.x, rect.y, w, rect.height)


def _bag_rect(rect):
    from pygame import Rect
    dr = _doll_rect(rect)
    return Rect(dr.right + 12, rect.y, rect.right - dr.right - 12,
                rect.height)


def slot_rects(rect):
    """slot_value -> Rect, arranged around the mannequin."""
    from pygame import Rect
    dr = _doll_rect(rect)
    cx = dr.x + dr.width // 2
    cy = dr.y + int(dr.height * 0.48)
    s = SLOT_SIZE
    # (dx, dy) in slot-size units from the figure centre
    off = {
        "amulet": (0, -2.4), "armor": (0, -0.6),
        "weapon": (-2.1, -0.4), "shield": (2.1, -0.4),
        "ring": (2.1, 0.9), "boots": (0, 2.1),
    }
    out = {}
    for slot, (dx, dy) in off.items():
        out[slot] = Rect(int(cx + dx * s - s / 2),
                         int(cy + dy * s - s / 2), s, s)
    return out


def bag_rects(rect, n):
    from pygame import Rect
    br = _bag_rect(rect)
    x0 = br.x + 8
    y0 = br.y + 30
    out = []
    for i in range(n):
        c = i % BAG_COLS
        r = i // BAG_COLS
        out.append(Rect(x0 + c * (CELL + CELL_PAD),
                        y0 + r * (CELL + CELL_PAD), CELL, CELL))
    return out


def slot_at(pos, rect):
    for slot, r in slot_rects(rect).items():
        if r.collidepoint(pos):
            return slot
    return None


def bag_index_at(pos, rect, n):
    for i, r in enumerate(bag_rects(rect, n)):
        if r.collidepoint(pos):
            return i
    return None


# ---- drop logic (pure) ------------------------------------------------

def can_equip_to(item, slot_value):
    try:
        s = eqp.slot_for_item(item)
        return s is not None and s.value == slot_value
    except Exception:
        return False


def apply_drop(engine, origin, target):
    """Resolve a drag from `origin` to `target`. Each is ("bag", idx),
    ("slot", slot_value) or None. Returns a status string ("" = nothing)."""
    player = engine.player
    if origin is None or target is None or origin == target:
        # a plain click on a bag item equips it; on a slot, unequips it
        return _click_action(engine, origin)
    okind, oval = origin
    tkind, tval = target
    if okind == "bag" and tkind == "slot":
        item = _bag_item(player, oval)
        if item is not None and can_equip_to(item, tval):
            return eqp.equip(player, item)
        return ""
    if okind == "slot" and tkind == "bag":
        return _unequip(engine, oval)
    if okind == "bag" and tkind == "bag":
        return ""                          # reordering not modelled
    return ""


def _click_action(engine, origin):
    if origin is None:
        return ""
    kind, val = origin
    player = engine.player
    if kind == "bag":
        item = _bag_item(player, val)
        if item is not None and eqp.slot_for_item(item) is not None:
            return eqp.equip(player, item)
        return ""
    if kind == "slot":
        return _unequip(engine, val)
    return ""


def _unequip(engine, slot_value):
    for s in eqp.EquipSlot:
        if s.value == slot_value:
            return eqp.unequip(engine.player, s)
    return ""


def _bag_item(player, idx):
    inv = player.inventory
    if 0 <= idx < len(inv):
        return inv[idx]
    return None


# ---- drawing ----------------------------------------------------------

def _icon(gui, item, size):
    try:
        spr = gui.renderer.sprites.item(getattr(item, "name", ""))
        return pygame.transform.smoothscale(spr, (size, size))
    except Exception:
        return None


_RARITY = {"common": (170, 170, 170), "uncommon": (90, 200, 110),
           "rare": (90, 150, 230), "epic": (180, 110, 220),
           "legendary": (230, 170, 70)}


def _rarity_color(item):
    r = getattr(getattr(item, "rarity", None), "value", "common")
    return _RARITY.get(r, (150, 150, 150))


def draw_equipment(target, rect, gui, hub, font, small):
    engine = gui.engine
    player = engine.player
    dr = _doll_rect(rect)
    # a simple mannequin silhouette
    cx = dr.x + dr.width // 2
    cy = dr.y + int(dr.height * 0.48)
    body = (70, 74, 92)
    pygame.draw.circle(target, body, (cx, cy - int(SLOT_SIZE * 1.5)), 16)
    pygame.draw.rect(target, body,
                     (cx - 20, cy - int(SLOT_SIZE * 1.0), 40, 78),
                     border_radius=8)
    pygame.draw.rect(target, body,
                     (cx - 26, cy - int(SLOT_SIZE * 0.9), 12, 60),
                     border_radius=6)
    pygame.draw.rect(target, body,
                     (cx + 14, cy - int(SLOT_SIZE * 0.9), 12, 60),
                     border_radius=6)

    eq = eqp.get_equipment(player)
    for slot, r in slot_rects(rect).items():
        item = eq.get(slot)
        pygame.draw.rect(target, (28, 30, 40), r, border_radius=6)
        col = _rarity_color(item) if item else (80, 84, 100)
        pygame.draw.rect(target, col, r, 2, border_radius=6)
        if item is not None:
            ic = _icon(gui, item, r.width - 14)
            if ic is not None:
                target.blit(ic, (r.x + 7, r.y + 7))
        else:
            lbl = small.render(SLOT_LABEL[slot], True, (110, 114, 130))
            target.blit(lbl, (r.centerx - lbl.get_width() // 2,
                              r.centery - lbl.get_height() // 2))

    # bags
    br = _bag_rect(rect)
    cap = _cap(engine)
    hdr = small.render(f"BAG  ({len(player.inventory)}"
                       + (f"/{cap}" if cap else "") + ")", True, (200, 200, 180))
    target.blit(hdr, (br.x + 8, br.y + 8))
    rects = bag_rects(rect, len(player.inventory))
    mouse = pygame.mouse.get_pos()
    hover = None
    for i, r in enumerate(rects):
        if not rect.contains(r):
            continue
        item = player.inventory[i]
        pygame.draw.rect(target, (26, 28, 36), r, border_radius=5)
        pygame.draw.rect(target, _rarity_color(item), r, 1, border_radius=5)
        ic = _icon(gui, item, r.width - 12)
        if ic is not None:
            target.blit(ic, (r.x + 6, r.y + 6))
        q = getattr(item, "quantity", 1)
        if q and q > 1:
            qs = small.render(str(q), True, (235, 235, 210))
            target.blit(qs, (r.right - qs.get_width() - 3,
                             r.bottom - qs.get_height() - 2))
        if r.collidepoint(mouse):
            hover = item

    # a dragged item rides the cursor
    drag = hub.drag
    if drag is not None and drag.get("item") is not None:
        ic = _icon(gui, drag["item"], CELL - 8)
        mx, my = mouse
        if ic is not None:
            target.blit(ic, (mx - (CELL - 8) // 2, my - (CELL - 8) // 2))

    # a hover tooltip
    if hover is not None and drag is None:
        _tooltip(target, rect, hover, font, small, mouse)


def _cap(engine):
    try:
        return engine.carry.capacity(engine.player)
    except Exception:
        return 0


def _tooltip(target, rect, item, font, small, mouse):
    name = getattr(item, "name", "?")
    lines = [name]
    itype = getattr(getattr(item, "item_type", None), "value", "")
    rar = getattr(getattr(item, "rarity", None), "value", "")
    if itype or rar:
        lines.append(f"{rar} {itype}".strip())
    for k, v in (getattr(item, "equip_bonuses", None) or {}).items():
        lines.append(f"{k} {v:+}")
    val = getattr(item, "value", None)
    if val:
        lines.append(f"worth ~{val}g")
    w = max(font.size(lines[0])[0], *[small.size(l)[0] for l in lines[1:]]
            ) + 16 if len(lines) > 1 else font.size(lines[0])[0] + 16
    h = 8 + font.get_height() + (len(lines) - 1) * (small.get_height() + 2) + 8
    mx, my = mouse
    x = min(mx + 14, rect.right - w)
    y = min(my + 8, rect.bottom - h)
    box = pygame.Rect(x, y, w, h)
    pygame.draw.rect(target, (18, 20, 28), box, border_radius=6)
    pygame.draw.rect(target, (120, 124, 150), box, 1, border_radius=6)
    target.blit(font.render(lines[0], True, _rarity_color(item)),
                (x + 8, y + 6))
    yy = y + 8 + font.get_height()
    for l in lines[1:]:
        target.blit(small.render(l, True, (205, 205, 195)), (x + 8, yy))
        yy += small.get_height() + 2


# ---- event handling ---------------------------------------------------

def handle_event(event, gui, hub, rect):
    if not PYGAME_OK:
        return False
    player = gui.engine.player
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        origin = _pick(event.pos, rect, player)
        if origin is not None:
            item = (_bag_item(player, origin[1]) if origin[0] == "bag"
                    else eqp.get_equipment(player).get(origin[1]))
            if item is not None:
                hub.drag = {"item": item, "origin": origin}
        return True
    if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and hub.drag:
        target = _pick(event.pos, rect, player, empty_ok=True)
        msg = apply_drop(gui.engine, hub.drag["origin"], target)
        hub.drag = None
        if msg:
            try:
                gui.engine.memory_manager.add_event(msg)
            except Exception:
                pass
        return True
    return False


def _pick(pos, rect, player, empty_ok=False):
    """What is under `pos`: ("slot", val), ("bag", idx) or None."""
    slot = slot_at(pos, rect)
    if slot is not None:
        return ("slot", slot)
    idx = bag_index_at(pos, rect, len(player.inventory))
    if idx is not None:
        return ("bag", idx)
    if empty_ok and _bag_rect(rect).collidepoint(pos):
        return ("bag", -1)            # dropped in empty bag space → unequip
    return None
