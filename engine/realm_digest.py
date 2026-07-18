"""T2.3 — surface the simulation.

A player-facing 'State of the Realm' digest of the live nightly sim — faction
strengths & wars, tribe threat levels, a lurking nemesis — so the churning
simulation is VISIBLE (the world-sim review found it manifested only as grey
[Realm] log lines, with no window into the state). Shown at the foot of the
Y-journal. Pure/read-only; every source queried defensively.
"""

_FACTION_NAMES = {
    "villagers": "The Townsfolk", "brigands": "The Brigands",
    "guards": "The Watch", "merchants": "The Merchants",
}


def _rank(s: int) -> str:
    return ("commanding" if s >= 70 else "strong" if s >= 50
            else "steady" if s >= 30 else "waning")


def _factions(engine) -> list:
    out = []
    try:
        state = engine.faction_ticker.state
    except Exception:
        return out
    ag = getattr(engine, "faction_agendas", None)
    for fid, s in state.items():
        st = int(s.get("strength", 0))
        line = f"  {_FACTION_NAMES.get(fid, fid.title())}: {_rank(st)} ({st})"
        try:
            if ag is not None:
                foe = next((o for o in state
                            if o != fid and ag.at_war(fid, o)), None)
                if foe:
                    line += f" — at war with {_FACTION_NAMES.get(foe, foe.title())}"
        except Exception:
            pass
        out.append(line)
    return out


def _tribes(engine) -> list:
    out = []
    try:
        mt = engine.monster_tribes
        strength = mt.strength
        specs = mt._tribes()
    except Exception:
        return out
    for tid, st in strength.items():
        name = specs.get(tid, {}).get("name", tid.replace("_", " ").title())
        threat = ("massing to raid!" if st >= 70 else "restless" if st >= 45
                  else "quiet")
        out.append(f"  {name}: {threat} ({int(st)})")
    return out


def _nemesis(engine) -> list:
    out = []
    try:
        for rec in engine.nemesis.nemeses.values():
            nm = rec.get("name", "A nemesis")
            title = rec.get("title", "")
            out.append(f"  {nm}{(' ' + title) if title else ''} still hunts you.")
    except Exception:
        pass
    return out


def lines(engine) -> list:
    """The 'State of the Realm' journal section."""
    body = _factions(engine) + _tribes(engine) + _nemesis(engine)
    if not body:
        body = ["  All is quiet across the realm."]
    return ["", "State of the Realm", "(how the land fares now)", ""] + body
