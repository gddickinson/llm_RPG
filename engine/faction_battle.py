"""P17.8 fold-back: off-screen faction skirmishes settled by the real
Lanchester resolver (`battle_resolve`) instead of a single die.

A faction's abstract STRENGTH (0-100) becomes a plausible little ARMY —
more strength = more bodies, and the faction's character picks the troop
types (guards field spears + swords + a few bows, brigands a light
mounted rabble, monsters beasts). `resolve()` fights it deterministically;
the survivor ratios fold back into the strength deltas the ticker
applies. So a raid isn't a coin-flip any more — spearmen turning a
brigand cavalry rush, or a beast warband routing a thin guard line,
actually decides it. Rosters are data (`data/battles/faction_armies.json`).
"""

from engine.battle.battle_data import _load
from engine.battle.battle_resolve import Army, resolve

_ARMIES = _load("faction_armies.json").get("rosters", {})

MIN_BODIES = 3               # even a spent faction fields a token force
BODIES_PER_STRENGTH = 2      # 0-100 strength -> up to ~50 soldiers


def _roster(faction: str):
    return _ARMIES.get(faction, _ARMIES.get(
        "_default", [["infantry_sword", 1]]))


def army_for(faction: str, strength: float, name=None, forts=None) -> Army:
    """Dress a faction's strength as an Army: total body count scales
    with strength, split across its troop types by their shares. `forts`
    (fort-type strings) man the defender's walls in a siege (P17.8c)."""
    shares = _roster(faction)
    total = max(MIN_BODIES, int(strength) // BODIES_PER_STRENGTH)
    denom = sum(w for _, w in shares) or 1
    specs = []
    for utype, w in shares:
        n = int(round(total * w / denom))
        if n > 0:
            specs.append((utype, n))
    if not specs:                        # tiny strength — one token unit
        specs = [(shares[0][0], 1)]
    return Army.make(name or faction, specs, forts=forts)


def _summary(res: dict, atk_start: int, def_start: int) -> dict:
    atk_surv = res["attacker_survivors"]
    def_surv = res["defender_survivors"]
    return {
        "winner": res["winner"],
        "atk_start": atk_start, "atk_survivors": atk_surv,
        "def_start": def_start, "def_survivors": def_surv,
        "atk_ratio": atk_surv / max(1, atk_start),
        "def_ratio": def_surv / max(1, def_start),
        "breached": res["breached"], "rounds": res["rounds"],
    }


def resolve_raid(atk_faction: str, atk_strength: float,
                 def_faction: str, def_strength: float,
                 rng=None, terrain: str = "plains",
                 is_siege: bool = False) -> dict:
    """Fight `atk_faction` against `def_faction`, each dressed from its
    strength. Returns the winner faction and both sides' survivor ratios
    (1.0 = untouched, 0.0 = wiped) so the caller can shed strength in
    proportion to the mauling."""
    atk = army_for(atk_faction, atk_strength, atk_faction)
    dfn = army_for(def_faction, def_strength, def_faction)
    seed = rng.randint(0, 2 ** 31 - 1) if rng is not None else 0
    res = resolve(atk, dfn, terrain=terrain, is_siege=is_siege, seed=seed)
    return _summary(res, atk.survivors(), dfn.survivors())


def resolve_siege(atk_faction: str, atk_strength: float,
                  def_faction: str, def_strength: float,
                  rng=None, fort: str = "stone_wall",
                  terrain: str = "plains") -> dict:
    """A CASTLE ASSAULT settled off-screen (P17.8c): the defender fights
    from behind a `fort`, so the resolver's siege math applies — an
    unbreached wall keeps the besiegers off (they inflict little) until
    their SIEGE ENGINES batter it down. So a walled garrison shrugs off a
    rabble that has no engines, but a proper besieging host with rams and
    catapults can breach and storm it. Same shape as `resolve_raid`, plus
    `breached`."""
    atk = army_for(atk_faction, atk_strength, atk_faction)
    dfn = army_for(def_faction, def_strength, def_faction, forts=[fort])
    seed = rng.randint(0, 2 ** 31 - 1) if rng is not None else 0
    res = resolve(atk, dfn, terrain=terrain, is_siege=True,
                  seed=seed, max_rounds=20)
    return _summary(res, atk.survivors(), dfn.survivors())
