"""The Training tab of the Character Hub (the skills/spells upgrade).

Spend the Training Points a level-up granted — but only when standing at
a trainer suited to your calling. Shows your points, the trainer (or where
to find one), and the skills + spells on offer; ↑/↓ select, Enter/click to
train. The option list + spend go through `engine/training`.
"""

try:
    import pygame
    PYGAME_OK = True
except ImportError:                       # pragma: no cover
    PYGAME_OK = False


def build_rows(engine):
    """(profile|None, rows) — rows are header/skill/spell dicts, in draw order."""
    from engine import training
    prof = training.trainer_here(engine)
    rows = []
    if prof is None:
        return None, rows
    tp = training.training_points(engine.player)
    sk = training.skill_options(engine, prof)
    if sk:
        rows.append({"type": "header", "text": "SKILLS  (1 point each)"})
        for sid, name, lvl, at_cap in sk:
            ok = (not at_cap) and tp >= training.SKILL_TP
            reason = "at cap — practise afield" if at_cap else (
                "" if ok else "need a point")
            rows.append({"type": "skill", "id": sid,
                         "label": f"{name:<14} Lv {lvl}", "ok": ok,
                         "reason": reason})
    if prof.get("teaches_spells"):
        sp = training.spell_options(engine, prof)
        if sp:
            rows.append({"type": "header", "text": "SPELLS  (2 points each)"})
            for sid, name, tier, school in sp:
                ok = tp >= training.SPELL_TP
                rows.append({"type": "spell", "id": sid,
                             "label": f"{name}  (T{tier} {school})",
                             "ok": ok, "reason": "" if ok else "need 2 points"})
    return prof, rows


def _actions(rows):
    return [r for r in rows if r["type"] in ("skill", "spell")]


def execute(engine, hub):
    """Train the currently-selected row. Returns a status string or None."""
    _, rows = build_rows(engine)
    acts = _actions(rows)
    if not acts:
        return None
    row = acts[max(0, min(hub.train_cursor, len(acts) - 1))]
    from engine import training
    if row["type"] == "skill":
        ok, msg = training.train_skill(engine, row["id"])
    else:
        ok, msg = training.learn_spell(engine, row["id"])
    try:
        engine.memory_manager.add_event(msg)
    except Exception:
        pass
    return msg


# ---- drawing / input ---------------------------------------------------

def draw_training(target, rect, gui, hub, f, small, big):
    engine = gui.engine
    from engine import training
    tp = training.training_points(engine.player)
    title = big.render("Training", True, (240, 220, 140))
    target.blit(title, (rect.x, rect.y))
    pts = f.render(f"Training points: {tp}", True,
                   (150, 220, 150) if tp else (170, 170, 170))
    target.blit(pts, (rect.x, rect.y + 30))

    prof, rows = build_rows(engine)
    y = rect.y + 62
    if prof is None:
        for ln in (
            "You have no trainer here.",
            "Seek one suited to your calling and stand by them:",
            "  • a guild hall or weapon master — martial skills",
            "  • a mage tower / library — spellcraft + arcane spells",
            "  • a temple — medicine + divine spells",
            "  • a grove or lodge — a ranger's & druid's craft",
            "  • any guild instructor or smith — the trade skills",
                "Then open this screen to spend your points."):
            col = (240, 220, 140) if ln.endswith(":") else (206, 206, 200)
            target.blit(f.render(ln, True, col), (rect.x, y))
            y += f.get_height() + 4
        return

    where = f.render("Trainer: " + " · ".join(prof["labels"]), True,
                     (200, 210, 235))
    target.blit(where, (rect.x, rect.y + 30 + f.get_height() + 2))
    y = rect.y + 30 + 2 * (f.get_height() + 4) + 8

    acts = _actions(rows)
    cur = max(0, min(hub.train_cursor, max(0, len(acts) - 1)))
    ai = 0
    lh = f.get_height() + 5
    for r in rows:
        if r["type"] == "header":
            y += 4
            target.blit(small.render(r["text"], True, (240, 220, 140)),
                        (rect.x, y))
            y += small.get_height() + 3
            continue
        sel = (ai == cur)
        if sel:
            pygame.draw.rect(target, (40, 44, 60),
                             (rect.x - 4, y - 2, rect.width - 8, lh),
                             border_radius=4)
        col = ((235, 235, 210) if r["ok"] else (130, 132, 140))
        if sel:
            col = (255, 240, 160) if r["ok"] else (170, 150, 120)
        line = f"  {'>' if sel else ' '} {r['label']}"
        target.blit(f.render(line, True, col), (rect.x, y))
        if r["reason"]:
            rr = small.render(r["reason"], True, (150, 130, 110))
            target.blit(rr, (rect.x + rect.width - rr.get_width() - 20,
                             y + 2))
        y += lh
        ai += 1
    if acts:
        hint = small.render("Up/Down choose  -  Enter / click to train", True,
                            (150, 152, 168))
        target.blit(hint, (rect.x, rect.bottom - 18))


def handle_key(event, gui, hub):
    if not PYGAME_OK:
        return True
    _, rows = build_rows(gui.engine)
    n = len(_actions(rows))
    k = event.key
    if k in (pygame.K_DOWN, pygame.K_s) and n:
        hub.train_cursor = (hub.train_cursor + 1) % n
    elif k in (pygame.K_UP, pygame.K_w) and n:
        hub.train_cursor = (hub.train_cursor - 1) % n
    elif k in (pygame.K_RETURN, pygame.K_SPACE) and n:
        execute(gui.engine, hub)
    return True


def handle_click(pos, rect, gui, hub):
    """Map a click to an option row (rough row math mirroring the draw)."""
    _, rows = build_rows(gui.engine)
    acts = _actions(rows)
    if not acts:
        return True
    # walk the same layout to find the clicked action index
    f_h = gui.player_screen._f.get_height()
    y = rect.y + 30 + 2 * (f_h + 4) + 8
    lh = f_h + 5
    sh = gui.player_screen._small.get_height()
    ai = 0
    for r in rows:
        if r["type"] == "header":
            y += 4 + sh + 3
            continue
        if y <= pos[1] < y + lh:
            hub.train_cursor = ai
            execute(gui.engine, hub)
            return True
        y += lh
        ai += 1
    return True
