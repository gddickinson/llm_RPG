"""OAKVALE T5b — the large-town REGION (`world_kind="oakvale"`).

A dedicated, bigger world whose centrepiece is the big procedurally-generated
Oakvale (the reusable `world/town/` generator), so George can walk and playtest
it without disturbing the classic 120×80 world. This module lays the setting —
a grass basin ringed by forest, a river threading through (the town's streets
BRIDGE it), and a mountain shoulder — then plans + stamps Oakvale at the centre.
The living countryside (supporting villages, farms, terrain-aware roads, wells)
is added by T7; the Deepdelve entrance + in-town adventures by T9.

`region_size(world_kind)` gives the engine the bigger map; `build_oakvale_region`
plants everything and returns the plan + player spawn.
"""

import logging
import random

from world.location import Location
from world.town.stamp import stamp_town
from world.town.town_gen import plan_town
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.oakvale_region")

REGION_SIZE = (190, 140)          # room for a big town + countryside
OAKVALE_RADIUS = 42


def region_size(world_kind: str):
    """The map (width, height) for a world kind, or None for the default."""
    return REGION_SIZE if world_kind == "oakvale" else None


def _fill_grass(wm) -> None:
    for y in range(wm.height):
        for x in range(wm.width):
            wm.terrain[y][x] = TerrainType.GRASS


def _forest_ring(wm, rng) -> None:
    """A broken forest border + a few inland copses."""
    W, H = wm.width, wm.height
    for y in range(H):
        for x in range(W):
            edge = min(x, y, W - 1 - x, H - 1 - y)
            if edge < 4 and rng.random() < 0.55:
                wm.terrain[y][x] = TerrainType.FOREST
    for _ in range((W * H) // 500):
        cx, cy = rng.randint(4, W - 5), rng.randint(4, H - 5)
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                x, y = cx + dx, cy + dy
                if 0 <= x < W and 0 <= y < H and dx * dx + dy * dy <= 9 \
                        and rng.random() < 0.6:
                    wm.terrain[y][x] = TerrainType.FOREST


def _river(wm, rng) -> None:
    """A meandering river down the map (steepest-ish descent with wander)."""
    W, H = wm.width, wm.height
    x = rng.randint(W // 3, 2 * W // 3)
    for y in range(H):
        for dx in (-1, 0):                       # a 2-wide river
            if 0 <= x + dx < W:
                wm.terrain[y][x + dx] = TerrainType.WATER
        x += rng.choice((-1, 0, 0, 1))
        x = max(2, min(W - 3, x))


def _mountains(wm, rng) -> None:
    """A mountain shoulder along the north-east."""
    W, H = wm.width, wm.height
    for y in range(0, H // 4):
        for x in range(3 * W // 4, W):
            if rng.random() < 0.5:
                wm.terrain[y][x] = TerrainType.MOUNTAIN
    wm  # noqa
    from world.location import Location as _L
    return _L("Cragfell Heights", "Grey mountains along the northern march.",
              3 * W // 4, 0, W - 3 * W // 4, H // 4)


def build_oakvale_region(world, seed: int = 7) -> dict:
    """Plant the Oakvale region: setting terrain + the big walled town."""
    wm = world.map
    rng = random.Random(seed)
    _fill_grass(wm)
    _forest_ring(wm, rng)
    _river(wm, rng)
    mtn = _mountains(wm, rng)
    if mtn is not None:
        world.add_location(mtn)
    cx, cy = wm.width // 2, wm.height // 2
    plan = plan_town(cx, cy, OAKVALE_RADIUS, size="town", seed=seed)
    res = stamp_town(world, plan, name="Oakvale")
    logger.info("Oakvale region planted: %s", res)
    out = {"town": "Oakvale", "center": (cx, cy), "plan": plan}
    out.update(res)
    _plant_arrival_waystone(world, cx, cy)          # the hero arrives on this
    out["grate"] = _plant_sewer_grate(world, cx, cy)  # a visible Deepdelve way in
    # T7 the living countryside — supporting villages, farms, roads + bridges
    try:
        from world.town.countryside import build_countryside
        out["villages"] = build_countryside(world, (cx, cy),
                                            OAKVALE_RADIUS, seed=seed)
    except Exception as e:                           # pragma: no cover
        logger.warning("countryside build failed: %s", e)
        out["villages"] = []
    return out


def _plant_arrival_waystone(world, cx, cy):
    """A teleport DIAS at the market square — the hero arrives on it, as if
    stepping off the Wayfarers' network into the town."""
    from world.location import Location
    wm = world.map
    if wm.terrain[cy][cx] == TerrainType.WATER:
        wm.terrain[cy][cx] = TerrainType.ROAD
    loc = Location("Oakvale Waystone",
                   "A rune-circle waystone in the market square, where "
                   "travellers step in from afar.", cx, cy, 1, 1)
    loc.add_property("waystone", "waystone_oakvale")
    world.add_location(loc)
    return (cx, cy)


def _grate_spot(wm, cx, cy):
    """A road/plaza tile a few paces off the square for the sewer grate."""
    for r in range(3, 12):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < wm.width and 0 <= y < wm.height \
                        and wm.terrain[y][x] == TerrainType.ROAD:
                    return (x, y)
    return None


def _plant_sewer_grate(world, cx, cy):
    """A VISIBLE iron sewer grate in the street — an OBVIOUS way down into the
    Deepdelve (George: 'make the entrance more obvious, a grate/sewer entrance')."""
    from world.location import Location
    wm = world.map
    spot = _grate_spot(wm, cx, cy)
    if spot is None:
        return None
    gx, gy = spot
    wm.terrain[gy][gx] = TerrainType.CAVE
    loc = Location("The Oakvale Sewers",
                   "A rusted iron grate set in the cobbles, a stone stair "
                   "beneath it descending into the Deepdelve.", gx, gy, 1, 1)
    loc.add_property("dungeon_key", "deepdelve")
    loc.add_property("dungeon_name", "The Deepdelve")
    loc.add_property("deep_dungeon", True)
    loc.add_property("deep_levels", 6)
    loc.add_property("deepdelve_mouth", True)
    loc.add_property("sewer_grate", True)
    world.add_location(loc)
    return spot


def oakvale_spawn(world):
    """Where the player wakes — the market-square WAYSTONE (as if just
    arrived), else the square centre."""
    ws = next((l for l in world.locations
               if l.get_property("waystone") == "waystone_oakvale"), None)
    if ws is not None:
        return (ws.x, ws.y)
    town = next((l for l in world.locations
                 if l.name == "Oakvale" and l.get_property("town")), None)
    if town is None:
        return None
    cx, cy = town.center()
    wm = world.map
    if 0 <= cx < wm.width and 0 <= cy < wm.height and \
            wm.terrain[cy][cx] in (TerrainType.ROAD, TerrainType.GRASS,
                                   TerrainType.BRIDGE):
        return (cx, cy)
    # else a nearby walkable tile
    for r in range(1, 8):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < wm.width and 0 <= y < wm.height and \
                        wm.terrain[y][x] in (TerrainType.ROAD, TerrainType.GRASS):
                    return (x, y)
    return (cx, cy)
