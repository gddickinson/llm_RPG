"""The Bloodstone realm layout (P18.4) — the castle, its gate town, and a
ring of farming villages that supply it.

`build_castle_region(world)` plants a whole region on the world map: the
FORTRESS footprint (the P18.1-3 castle structure attaches to the
"Bloodstone Castle" location, so this doubles as the P18.3b overworld
footprint — a walled keep with a gatehouse), the town of Kingsgate at the
gate (inn, market, temple, smithy), and a ring of farming villages whose
FARMLAND feeds the crown (the P8.3 farms + P16 production chain do the
rest). Roads stitch the supply routes together.

Pure over a `world`; used at world-build time and by the P18.5 "Begin at
the Castle" start. Returns the names of what it planted.
"""

import logging

from world.location import Location
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.castle_region")

CASTLE_NAME = "Bloodstone Castle"
TOWN_NAME = "Kingsgate Town"
VILLAGES = ("Wheatfield Village", "Millbrook Village", "Greenhollow Hamlet")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _tag(loc: Location) -> None:
    low = loc.name.lower()
    if "smith" in low or "forge" in low:
        loc.add_property("type", "forge")
        loc.add_property("forge", True)
    elif "inn" in low or "rest" in low or "tavern" in low:
        loc.add_property("type", "tavern")
    elif "temple" in low or "shrine" in low or "chapel" in low:
        loc.add_property("type", "temple")
    elif "market" in low or "shop" in low or "store" in low:
        loc.add_property("type", "shop")


def _building(world, x, y, w, h, name, desc) -> None:
    wm = world.map
    x2, y2 = min(x + w, wm.width), min(y + h, wm.height)
    for yy in range(max(0, y), y2):
        for xx in range(max(0, x), x2):
            wm.terrain[yy][xx] = TerrainType.BUILDING
    loc = Location(name, desc, x, y, x2 - x, y2 - y)
    _tag(loc)
    world.add_location(loc)


def _road(world, ax, ay, bx, by) -> None:
    """An L-shaped road; water crossings become bridges, buildings kept."""
    wm = world.map

    def lay(x, y):
        if not (0 <= x < wm.width and 0 <= y < wm.height):
            return
        t = wm.terrain[y][x]
        if t == TerrainType.WATER:
            wm.terrain[y][x] = TerrainType.BRIDGE
        elif t != TerrainType.BUILDING:
            wm.terrain[y][x] = TerrainType.ROAD

    for x in range(min(ax, bx), max(ax, bx) + 1):
        lay(x, ay)
    for y in range(min(ay, by), max(ay, by) + 1):
        lay(bx, y)


def _fortress(world, cx, cy, fw, fh) -> tuple:
    """A curtain-walled keep with a gatehouse in the south wall. The whole
    footprint is the 'Bloodstone Castle' location the structure attaches
    to. Returns the gate tile."""
    wm = world.map
    x0, y0 = cx - fw // 2, cy - fh // 2
    x1, y1 = x0 + fw, y0 + fh
    gate_x = cx
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            if not (0 <= xx < wm.width and 0 <= yy < wm.height):
                continue
            on_wall = (xx in (x0, x1 - 1) or yy in (y0, y1 - 1))
            if on_wall and not (yy == y1 - 1 and xx == gate_x):
                wm.terrain[yy][xx] = TerrainType.BUILDING   # curtain wall
            elif yy == y1 - 1 and xx == gate_x:
                wm.terrain[yy][xx] = TerrainType.ROAD        # the gatehouse
            else:
                wm.terrain[yy][xx] = TerrainType.GRASS       # the bailey
    loc = Location(CASTLE_NAME,
                   "A great curtain-walled fortress, banners snapping over "
                   "the gatehouse — the seat of the kings of Bloodstone.",
                   x0, y0, fw, fh)
    loc.add_property("type", "castle")
    world.add_location(loc)
    return (gate_x, min(wm.height - 1, y1))


def _town(world, x, y) -> None:
    wm = world.map
    x = _clamp(x, 1, wm.width - 11)
    y = _clamp(y, 1, wm.height - 7)
    world.add_location(Location(
        TOWN_NAME,
        "The bustling town at the castle gate, fed fat on the crown's "
        "custom.", x, y, 10, 6))
    _building(world, x + 1, y + 1, 2, 2, "The King's Rest Inn",
              "A busy inn hard by the castle gate.")
    _building(world, x + 5, y + 1, 2, 2, "Kingsgate Market",
              "Stalls of grain, cloth and iron for the castle's needs.")
    _building(world, x + 1, y + 3, 2, 2, "Temple of the Crown",
              "A stone temple where the town prays for the King's health.")
    _building(world, x + 5, y + 3, 2, 2, "The Royal Smithy",
              "The forge that shoes the cavalry and mends the guard's steel.")


def _village(world, x, y, name) -> None:
    """A small farming settlement: a farmhouse and a patch of FARMLAND the
    P8.3/P16 systems bring to life."""
    wm = world.map
    x = _clamp(x, 2, wm.width - 8)
    y = _clamp(y, 2, wm.height - 8)
    world.add_location(Location(
        name, f"A farming village of thatch and hedgerow that sends its "
        f"grain to the castle.", x, y, 6, 4))
    _building(world, x + 1, y + 1, 2, 2, f"{name.split()[0]} Farmhouse",
              "A stout farmhouse, its yard full of geese.")
    # a field of farmland beside the houses
    for yy in range(y, min(wm.height, y + 4)):
        for xx in range(x + 3, min(wm.width, x + 7)):
            if wm.terrain[yy][xx] == TerrainType.GRASS:
                wm.terrain[yy][xx] = TerrainType.FARMLAND


def build_castle_region(world) -> dict:
    """Plant the castle, its town and the supply villages; link them by
    road. Returns {'castle','town','villages',...} for the caller."""
    w, h = world.map.width, world.map.height
    cx, cy = w // 2, h // 2 - 4
    gate = _fortress(world, cx, cy, 16, 12)
    town_x, town_y = cx - 5, gate[1] + 2
    _town(world, town_x, town_y)
    _road(world, gate[0], gate[1], cx, town_y)

    sites = [(int(w * 0.15), int(h * 0.20)),
             (int(w * 0.82), int(h * 0.22)),
             (int(w * 0.50), min(h - 8, int(h * 0.85)))]
    for name, (vx, vy) in zip(VILLAGES, sites):
        _village(world, vx, vy, name)
        _road(world, vx + 3, vy + 1, cx, town_y + 3)   # supply route to town

    logger.info("Bloodstone realm planted: castle + town + %d villages",
                len(VILLAGES))
    return {"castle": CASTLE_NAME, "town": TOWN_NAME,
            "villages": list(VILLAGES)}
