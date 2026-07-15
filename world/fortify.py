"""P31.1 — fortify a town: ring it with a WALL and post GUARDS at the gates.

George: the starting town should be a walled, guarded town without monsters
wandering inside. P27.1 already makes a settlement's environs a no-spawn safe
zone; this adds the physical defences — a curtain wall around the town with
gates cut where the roads cross, and a guard standing at each gate.

Pure geometry over the `WorldMap` (`fortify`), plus a small `post_guards`
helper that needs the engine's NPC manager. Reusable for any settlement (the
same approach `castle_region` uses for the Bloodstone keep).
"""

import logging

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.fortify")

WALL = TerrainType.BUILDING          # a wall reads as a solid building tile
GATE = TerrainType.ROAD              # a gate is a passable road tile
# terrain a wall never overwrites — roads/bridges become GATES, water and
# mountains are natural barriers left as they are
_GATE_TERRAIN = (TerrainType.ROAD, TerrainType.BRIDGE)
_NATURAL_BARRIER = (TerrainType.WATER, TerrainType.MOUNTAIN)


def town_bounds(location, margin: int = 2):
    """The wall-ring box around a settlement Location — its footprint plus a
    `margin` of open ground (a courtyard) so the interior stays connected."""
    return (location.x - margin, location.y - margin,
            location.x + location.width + margin - 1,
            location.y + location.height + margin - 1)


def extent(locations, margin: int = 2):
    """The bounding box over SEVERAL locations plus a margin courtyard — so the
    wall can encompass a whole town (the village AND its library/forge/market),
    not just one footprint (P31.1b)."""
    x0 = min(l.x for l in locations) - margin
    y0 = min(l.y for l in locations) - margin
    x1 = max(l.x + l.width - 1 for l in locations) + margin
    y1 = max(l.y + l.height - 1 for l in locations) + margin
    return x0, y0, x1, y1


def _has_building_tile(wmap, loc) -> bool:
    for y in range(max(0, loc.y), min(wmap.height, loc.y + loc.height)):
        for x in range(max(0, loc.x), min(wmap.width, loc.x + loc.width)):
            if wmap.terrain[y][x] == TerrainType.BUILDING:
                return True
    return False


def town_members(world, center_loc, radius: int = 12):
    """The buildings that belong to the town: the centre settlement plus every
    nearby location whose footprint sits on a BUILDING tile (the library, forge,
    market are walled in; a distant wilderness feature is not)."""
    wmap = world.map
    cx, cy = center_loc.center()
    out = [center_loc]
    for loc in getattr(world, "locations", []):
        if loc is center_loc:
            continue
        lx, ly = loc.center()
        if max(abs(lx - cx), abs(ly - cy)) > radius:
            continue
        if _has_building_tile(wmap, loc):
            out.append(loc)
    return out


def _clamp(wmap, x0, y0, x1, y1):
    return (max(0, x0), max(0, y0),
            min(wmap.width - 1, x1), min(wmap.height - 1, y1))


def _perimeter(x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        yield (x, y0)
        yield (x, y1)
    for y in range(y0 + 1, y1):
        yield (x0, y)
        yield (x1, y)


def _ring(wmap, x0, y0, x1, y1):
    """Wall the perimeter of the box. A perimeter tile already carrying a ROAD
    stays a GATE; water/mountain are left as natural barriers; every other
    perimeter tile becomes WALL. If no road crosses, one gate is cut in the
    south edge. Returns the gate tiles."""
    x0, y0, x1, y1 = _clamp(wmap, x0, y0, x1, y1)
    gates = []
    for (x, y) in _perimeter(x0, y0, x1, y1):
        t = wmap.terrain[y][x]
        if t in _GATE_TERRAIN:
            gates.append((x, y))          # the road IS the gate
        elif t in _NATURAL_BARRIER:
            continue                      # leave the natural barrier
        else:
            wmap.terrain[y][x] = WALL
    if not gates:                          # no road crossed — cut one gate
        gx = (x0 + x1) // 2
        wmap.terrain[y1][gx] = GATE
        gates.append((gx, y1))
    return gates


_OUT = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


def _ensure_min_gates(wmap, x0, y0, x1, y1, gates, minimum: int = 2):
    """Cut extra gates on gate-less edges until the town has at least `minimum`
    on DIFFERENT sides — so a walled town is never a one-door prison (George:
    "no way through the four main walls"). A new gate needs open ground just
    outside it, never a cliff, lake, or another wall."""
    def edge_of(g):
        x, y = g
        if y == y0:
            return "north"
        if y == y1:
            return "south"
        if x == x0:
            return "west"
        return "east"

    have = {edge_of(g) for g in gates}
    mids = {"north": ((x0 + x1) // 2, y0), "south": ((x0 + x1) // 2, y1),
            "west": (x0, (y0 + y1) // 2), "east": (x1, (y0 + y1) // 2)}
    for side in ("south", "north", "east", "west"):
        if len(gates) >= minimum:
            break
        if side in have:
            continue
        gx, gy = mids[side]
        ox, oy = gx + _OUT[side][0], gy + _OUT[side][1]
        if not (0 <= ox < wmap.width and 0 <= oy < wmap.height):
            continue
        if wmap.terrain[oy][ox] in _NATURAL_BARRIER \
                or wmap.terrain[oy][ox] == WALL:
            continue                       # opens onto a barrier — try next edge
        wmap.terrain[gy][gx] = GATE
        gates.append((gx, gy))
        have.add(side)
    return gates


def fortify(wmap, location, margin: int = 2):
    """Wall a single location's perimeter (the base ring). Returns gate tiles."""
    gates = _ring(wmap, *town_bounds(location, margin))
    logger.info(f"Fortified {location.name}: {len(gates)} gate(s).")
    return gates


def fortify_town(world, center_loc, margin: int = 2, radius: int = 12):
    """P31.1b: wall the WHOLE town — the box enclosing the centre settlement AND
    its neighbouring buildings (library, forge, market…) — with a GUARD TOWER
    at each corner. Returns `{"gates": [...], "corners": [(x,y)×4]}`."""
    wmap = world.map
    members = town_members(world, center_loc, radius)
    x0, y0, x1, y1 = _clamp(wmap, *extent(members, margin))
    gates = _ring(wmap, x0, y0, x1, y1)
    _ensure_min_gates(wmap, x0, y0, x1, y1, gates, minimum=2)
    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    for cx, cy in corners:
        wmap.terrain[cy][cx] = WALL          # a solid tower block at the corner
    logger.info(f"Fortified {center_loc.name} town: {len(members)} buildings, "
                f"{len(gates)} gate(s), 4 towers.")
    return {"gates": gates, "corners": corners}


def post_guards(engine, gates) -> int:
    """Stand a guard just INSIDE each gate (a passable, unoccupied tile next
    to it). Returns the number posted. Idempotent-ish — call once at setup."""
    from characters.character_types import CharacterClass
    wmap = engine.world.map
    posted = 0
    for gx, gy in gates:
        spot = _guard_spot(wmap, gx, gy)
        if spot is None:
            continue
        try:
            guard = engine.npc_manager.create_random_npc(
                char_class=CharacterClass.GUARD)
        except Exception as e:
            logger.debug(f"guard create: {e}")
            continue
        guard.metadata["gate_guard"] = [gx, gy]
        wmap.remove_character(guard)
        guard.position = spot
        wmap.place_character(guard, *spot)
        posted += 1
    return posted


def post_towers(engine, corners) -> int:
    """P31.1b: plant a GUARD TOWER marker at each corner and post a tower guard
    beside it (P31.1c makes them spot & shoot). Returns towers manned."""
    from characters.character_types import CharacterClass
    from world.location import Location
    wmap = engine.world.map
    manned = 0
    for cx, cy in corners:
        loc = Location("Wall Tower", "A stone tower on the town wall, a "
                       "guard keeping watch from its roof.", cx, cy, 1, 1)
        loc.add_property("wall_tower", True)
        engine.world.add_location(loc)
        spot = _guard_spot(wmap, cx, cy)
        if spot is None:
            continue
        try:
            guard = engine.npc_manager.create_random_npc(
                char_class=CharacterClass.GUARD)
        except Exception as e:
            logger.debug(f"tower guard: {e}")
            continue
        guard.metadata["tower_guard"] = [cx, cy]
        wmap.remove_character(guard)
        guard.position = spot
        wmap.place_character(guard, *spot)
        manned += 1
    return manned


def _guard_spot(wmap, gx, gy):
    """A walkable, unoccupied tile BESIDE the gate/tower for the guard — never
    ON the gate tile itself, so the gate stays free to close (P31.1d)."""
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1)):
        x, y = gx + dx, gy + dy
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            continue
        if wmap.terrain[y][x] in (WALL, TerrainType.WATER,
                                  TerrainType.MOUNTAIN):
            continue
        if (x, y) in wmap.characters:
            continue
        return (x, y)
    return None
