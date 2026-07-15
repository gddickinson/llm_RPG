"""Fire & the battle surface layer (P17.E4).

Ports `engine/surfaces.py`'s DOS2-style fire onto the battle grid: a
sparse SURFACE layer (`field.surfaces`) of FIRE and OIL. A fire arrow,
battle-magic, or a cauldron of boiling oil IGNITES a tile; from there
flame BURNS whoever stands in it, EATS the flammable terrain it sits on
(a treeline or a hedge burns to bare scorched ground, so cover is gone),
GNAWS a wooden wall or gate to a breach, and SPREADS to neighbouring
combustibles — and a whole connected OIL pool goes up the instant flame
touches any part of it. Each fire burns down over a few ticks and leaves
scorched earth. Unifies the "trees and buildings can be set on fire"
ask, the P17.6e boiling oil, and the ignition side of P17.12 battle-magic
into one system the session ticks each round.
"""

FIRE_DURATION = 5           # ticks a fire burns before it gutters out
FIRE_DAMAGE = 4             # per tick to a soldier standing in flames
WALL_BURN = 6               # per tick to a flammable wall/gate
SPREAD_CHANCE = 0.35        # per adjacent combustible per tick
OIL_TURNS = 30             # how long a poured oil slick lingers

COMBUSTIBLE_TERRAIN = ("forest", "hedge")     # burns to "scorched"
_NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _flammable_struct(field, x, y) -> bool:
    k = field.struct_kind.get((x, y), "")
    return "gate" in k or "wood" in k or "timber" in k


def _soldier_at(field, x, y):
    sid = field.soldier_at(x, y)
    if not sid:
        return None
    for sq in field.squads.values():
        for s in sq.soldiers:
            if s.sid == sid:
                return s
    return None


# ---- ignition -------------------------------------------------------

def pour_oil(field, cx, cy, radius: int = 1, turns: int = OIL_TURNS) -> None:
    """Slick a patch of ground with oil (P17.6e / a broken cask) — it
    waits, harmless, until fire finds it."""
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            x, y = cx + dx, cy + dy
            if field.in_bounds(x, y) and not field.is_blocking(x, y):
                field.surfaces.setdefault((x, y),
                                          {"kind": "oil", "turns": turns})


def ignite(field, x, y, duration: int = FIRE_DURATION) -> None:
    """Set a tile alight. If it's oil, the whole connected pool catches."""
    if not field.in_bounds(x, y):
        return
    s = field.surfaces.get((x, y))
    if s and s["kind"] == "oil":
        _flood_oil(field, x, y, duration)
    else:
        field.surfaces[(x, y)] = {"kind": "fire", "turns": duration}


def _flood_oil(field, x, y, duration) -> None:
    stack, seen = [(x, y)], set()
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        s = field.surfaces.get(p)
        if not s or s["kind"] != "oil":
            continue
        field.surfaces[p] = {"kind": "fire", "turns": duration}
        for dx, dy in _NEIGH4:
            stack.append((p[0] + dx, p[1] + dy))


# ---- the per-tick simulation ----------------------------------------

def tick(field, rng) -> None:
    """One round of fire: burn, spread, then gutter down toward scorch."""
    if not field.surfaces:
        return
    for pos, s in list(field.surfaces.items()):
        if s.get("kind") == "fire":
            _burn(field, pos, s, rng)
    for pos in list(field.surfaces):
        s = field.surfaces.get(pos)
        if s is None:
            continue
        s["turns"] -= 1
        if s["turns"] <= 0:
            field.surfaces.pop(pos, None)
            if s["kind"] == "fire" and field.in_bounds(*pos):
                field.terrain[pos[1]][pos[0]] = "scorched"


def _burn(field, pos, s, rng) -> None:
    x, y = pos
    sol = _soldier_at(field, x, y)
    if sol is not None:
        sol.hurt(FIRE_DAMAGE)
        if not sol.alive:
            field.vacate(sol)
    if field.terrain[y][x] in COMBUSTIBLE_TERRAIN:
        field.terrain[y][x] = "scorched"       # the cover is consumed
    if _flammable_struct(field, x, y):
        field.damage_struct(x, y, WALL_BURN)     # a timber gate breaches
    for dx, dy in _NEIGH4:
        nx, ny = x + dx, y + dy
        if not field.in_bounds(nx, ny):
            continue
        n = field.surfaces.get((nx, ny))
        if n is not None:
            if n["kind"] == "oil":
                ignite(field, nx, ny, s["turns"])
            continue
        if (field.terrain[ny][nx] in COMBUSTIBLE_TERRAIN or
                _flammable_struct(field, nx, ny)) and \
                rng.random() < SPREAD_CHANCE:
            field.surfaces[(nx, ny)] = {"kind": "fire",
                                        "turns": FIRE_DURATION}
