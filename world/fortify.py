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


def _perimeter(x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        yield (x, y0)
        yield (x, y1)
    for y in range(y0 + 1, y1):
        yield (x0, y)
        yield (x1, y)


def fortify(wmap, location, margin: int = 2):
    """Wall the perimeter of a town. A perimeter tile already carrying a ROAD
    stays a GATE (passable); water/mountain are left as natural barriers;
    every other perimeter tile becomes WALL. If no road crosses the ring, one
    gate is cut in the south edge. Returns the list of gate tiles.
    """
    x0, y0, x1, y1 = town_bounds(location, margin)
    x0, y0 = max(0, x0), max(0, y0)
    x1 = min(wmap.width - 1, x1)
    y1 = min(wmap.height - 1, y1)
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
    logger.info(f"Fortified {location.name}: {len(gates)} gate(s).")
    return gates


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


def _guard_spot(wmap, gx, gy):
    """A walkable, unoccupied tile at or beside the gate for the guard."""
    for dx, dy in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)):
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
