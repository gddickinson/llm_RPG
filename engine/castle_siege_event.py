"""The living siege (P17.8d) — the castle is a target in the world sim.

When a hostile faction swells to war strength, it may raise a HOST and
march on the castle. The clash is settled off-screen by the resolver's
siege math (`faction_battle.resolve_siege`): the Bloodstone Guard fights
from behind its walls, so a raw host is turned back at the stone and its
army broken — but an overwhelming one (near the faction cap) can batter
the gate down and storm the keep. Either way the realm hears of it in a
`[Realm]` beat, and the losers pay for the day.

Fires once per game-day from the nightly stack; deterministic given the
engine's RNG.
"""

import logging

logger = logging.getLogger("llm_rpg.castle_siege")

HOSTILES = ("monsters", "brigands")
SIEGE_THRESHOLD = 65        # a faction must be this strong to raise a host
SIEGE_CHANCE = 0.12         # per eligible night
DEFAULT_GARRISON = 45
BROKEN_LOSS = 18            # strength a shattered host sheds


def _castle(engine):
    """The fortified castle in the world (the siege's target), or None."""
    for loc in engine.world.locations:
        if (loc.properties or {}).get("type") == "castle":
            return loc
    return None


def _pressure(engine):
    """The strongest hostile faction and its strength (the besieger)."""
    ft = getattr(engine, "faction_ticker", None)
    if ft is None:
        return ("brigands", 0)
    best, who = 0, "brigands"
    for f in HOSTILES:
        s = ft.state.get(f, {}).get("strength", 0)
        if s > best:
            best, who = s, f
    return (who, best)


def lay_siege(engine, castle, besieger: str, strength: float,
              rng) -> str:
    """Resolve a siege of `castle` by a `besieger` host of `strength`.
    Applies the consequences and returns the `[Realm]` beat."""
    from engine.faction_battle import resolve_siege
    garrison = int((castle.properties or {}).get("garrison",
                                                 DEFAULT_GARRISON))
    res = resolve_siege("besiegers", strength, "crown", garrison, rng)
    ft = getattr(engine, "faction_ticker", None)
    if res["winner"] == "crown":
        if ft and besieger in ft.state:
            ft.state[besieger]["strength"] = max(
                5, ft.state[besieger]["strength"] - BROKEN_LOSS)
        beat = (f"[Realm] The siege of {castle.name} was broken — the "
                f"walls held, and the {besieger} host shattered against "
                f"the stone.")
        castle.add_property("last_siege", "held")
    else:
        beat = (f"[Realm] {castle.name} has FALLEN — the {besieger} host "
                f"breached the gate and stormed the keep!")
        castle.add_property("fallen", True)
        castle.add_property("last_siege", "fell")
    engine.memory_manager.add_event(beat)
    return beat


def maybe_besiege(engine, rng):
    """Nightly: a strong-enough hostile faction may march on the castle.
    Returns the `[Realm]` beat, or None if no siege this night."""
    castle = _castle(engine)
    if castle is None or (castle.properties or {}).get("fallen"):
        return None
    besieger, strength = _pressure(engine)
    if strength < SIEGE_THRESHOLD:
        return None
    if rng.random() > SIEGE_CHANCE:
        return None
    return lay_siege(engine, castle, besieger, strength, rng)
