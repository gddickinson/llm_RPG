"""Content builders for the unified Character Hub (GAP.6) — pure, so they
are headless-testable. Each returns display lines for a tab; the hub's
generic text renderer draws them, treating a line ending in ':' or in
ALL-CAPS as a section header.
"""


def _mod(score):
    return (score - 10) // 2


def _sign(n):
    return f"+{n}" if n >= 0 else str(n)


def backstory(engine):
    """A short synthesized origin (there is no stored backstory field)."""
    p = engine.player
    race = getattr(p.race, "value", "wanderer")
    cls = getattr(p.character_class, "value", "adventurer")
    align = getattr(getattr(p, "alignment", None), "value", "neutral")
    ORIGINS = {
        "warrior": "drilled in the shield-wall before the beard came in",
        "wizard": "raised among dusty tomes and guttering candles",
        "rogue": "cut teeth in the alleys, quick of hand and quicker to vanish",
        "ranger": "born to the treeline, at home where the roads end",
        "cleric": "took vows young, and the vows took root",
        "bard": "sang for supper across a hundred tap-rooms",
        "merchant": "learned the weight of a coin before the weight of a blade",
    }
    seed = ORIGINS.get(cls, "came up hard and made your own way")
    return [
        f"A {align} {race} {cls}, {seed}.",
        f"Now {p.name} walks the road, ledger of deeds still being written.",
    ]


def character_lines(engine):
    p = engine.player
    lines = [
        f"{p.name}",
        f"Level {p.level} {getattr(p.race,'value','?')} "
        f"{getattr(p.character_class,'value','?')}"
        f"  ·  {getattr(getattr(p,'alignment',None),'value','neutral')}",
        "",
        "ATTRIBUTES",
    ]
    attrs = [("STR", p.strength), ("DEX", p.dexterity),
             ("CON", p.constitution), ("INT", p.intelligence),
             ("WIS", p.wisdom), ("CHA", p.charisma)]
    for name, score in attrs:
        lines.append(f"  {name}  {score:>2}  ({_sign(_mod(score))})")
    lines += ["", "CONDITION"]
    lines.append(f"  HP     {p.hp}/{p.max_hp}")
    meta = p.metadata or {}
    if "mana" in meta or "max_mana" in meta:
        lines.append(f"  Mana   {meta.get('mana',0)}/{meta.get('max_mana',0)}")
    try:
        from engine.effects import effective_ac
        lines.append(f"  Armour Class  {effective_ac(p)}")
    except Exception:
        pass
    try:
        cap = engine.carry.capacity(p)
        used = engine.carry.used_slots(p)
        lines.append(f"  Carry  {used}/{cap} slots")
    except Exception:
        pass
    lines.append(f"  Gold   {p.gold}")
    lines.append(f"  XP     {meta.get('xp', 0)}")
    try:
        lines.append("  " + engine.guild.status_line())
    except Exception:
        pass
    lines += ["", "BACKGROUND"]
    lines += ["  " + s for s in backstory(engine)]
    if getattr(p, "goals", None):
        lines += ["", "GOALS"] + [f"  * {g}" for g in p.goals]
    return lines


def _bar(frac, width=10):
    frac = max(0.0, min(1.0, frac))
    fill = int(round(frac * width))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def skills_lines(engine):
    p = engine.player
    out = ["SKILLS", ""]
    try:
        from engine.skill_progression import (all_skill_ids, skill_name,
                                              get_skill_level, get_skill_xp,
                                              total_xp_for_level,
                                              total_skill_level)
        for sid in all_skill_ids():
            lvl = get_skill_level(p, sid)
            xp = get_skill_xp(p, sid)
            base = total_xp_for_level(lvl)
            nxt = total_xp_for_level(lvl + 1)
            frac = (xp - base) / (nxt - base) if nxt > base else 1.0
            out.append(f"  {skill_name(sid):<13} Lv {lvl:>2}  "
                       f"{_bar(frac)} {int(frac*100):>3}%")
        out += ["", f"  Total skill level: {total_skill_level(p)}"]
    except Exception:
        out.append("  (skills unavailable)")
    try:
        from engine.skill_combat import combat_summary
        cs = combat_summary(p)
        if cs:
            out += ["", "COMBAT EDGE"] + [f"  {t}" for t in cs]
    except Exception:
        pass
    return out


def spells_lines(engine):
    p = engine.player
    known = (p.metadata or {}).get("spells_known", [])
    if not known:
        return ["SPELLS", "", "  You know no spells.",
                "  (Wizards, clerics and the like learn them by level or tome.)"]
    out = ["SPELLBOOK", ""]
    try:
        from engine.spells import SPELL_REGISTRY
        rows = []
        for sid in known:
            s = SPELL_REGISTRY.get(sid)
            if s is not None:
                rows.append(s)
        rows.sort(key=lambda s: (getattr(s, "tier", 1),
                                 getattr(s, "school", ""), s.name))
        for s in rows:
            school = getattr(s, "school", "")
            tier = getattr(s, "tier", 1)
            mana = getattr(s, "mana_cost", 0)
            out.append(f"  {s.name}  (T{tier} {school}, {mana} mana)")
            desc = getattr(s, "description", "") or ""
            if desc:
                out.append(f"      {desc}")
    except Exception:
        out.append("  (spellbook unavailable)")
    return out


def quests_lines(engine):
    out = ["QUESTS", ""]
    try:
        from quests.quest import QuestStatus
        qm = engine.quest_manager
        active = [q for q in qm.quests.values()
                  if q.status == QuestStatus.ACTIVE]
        done = [q for q in qm.quests.values()
                if q.status == QuestStatus.TURNED_IN]
        if active:
            out.append("ACTIVE")
            for q in active:
                out.append(f"  {q.name}")
                for obj in getattr(q, "objectives", []):
                    mark = "x" if getattr(obj, "completed", False) else " "
                    prog = _obj_progress(obj)
                    out.append(f"    [{mark}] {getattr(obj,'description','')}"
                               f"{prog}")
        else:
            out.append("  No active quests. Check a tavern board (E).")
        if done:
            out += ["", f"COMPLETED ({len(done)})"]
            for q in done[:12]:
                out.append(f"  * {q.name}")
    except Exception:
        out.append("  (quest log unavailable)")
    return out


def _obj_progress(obj):
    cur = getattr(obj, "current", None)
    req = getattr(obj, "required", None)
    if isinstance(cur, int) and isinstance(req, int) and req > 1:
        return f"  ({cur}/{req})"
    return ""


def journal_lines(engine):
    out = ["HISTORY & DEEDS", ""]
    got = False
    for src, header in ((_deeds, "RECENT DEEDS"),
                        (_chronicle, "CHRONICLE OF THE AGE"),
                        (_collection, "COLLECTION")):
        try:
            block = src(engine)
        except Exception:
            block = []
        if block:
            out += [header] + [f"  {b}" for b in block] + [""]
            got = True
    if not got:
        out.append("  Your legend is yet unwritten.")
    return out


def _deeds(engine):
    d = getattr(engine, "player_deeds", None)
    if d is None:
        return []
    for meth in ("recent_lines", "recent", "lines", "summary"):
        fn = getattr(d, meth, None)
        if callable(fn):
            try:
                res = fn()
                if res:
                    return [str(x) for x in res][:8]
            except Exception:
                pass
    return []


def _chronicle(engine):
    c = getattr(engine, "chronicle", None)
    if c is None:
        return []
    try:
        return [str(x) for x in c.lines()][:8]
    except Exception:
        return []


def _collection(engine):
    try:
        cl = engine.collection_log
        return [f"{cat.title()}: {len(cl.obtained(cat))}"
                for cat in ("items", "kills", "crafts", "places")]
    except Exception:
        return []
