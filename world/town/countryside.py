"""OAKVALE T7 — the living COUNTRYSIDE around the town.

A few supporting farming VILLAGES ring Oakvale, each a cluster of farmhouses +
cottages + a well + a chapel with FARMLAND fields worked by resident farmers,
connected back to a town gate by a terrain-aware ROAD (A* over the cost-field,
`world/road_astar.py`) that BRIDGES the river where it must cross. Broad farm
belts also stretch outside Oakvale's own walls. So the town is fed by a real
hinterland — fields, hamlets, and roads that make sense with the land.

`build_countryside(world, center, radius, seed)` plants the villages + farms +
roads and returns the village list; `populate_villages(engine, villages, seed)`
seats the farmers (called from `demo_setup` with the engine).
"""

import logging
import random

from world import road_astar
from world.location import Location
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.countryside")

VILLAGE_NAMES = ["Wheatfield", "Millbrook", "Greenhollow", "Thornby", "Ashcombe"]
_GRASS = TerrainType.GRASS
_BUILDING = TerrainType.BUILDING
_FARM = TerrainType.FARMLAND
_BLOCK = (TerrainType.WATER, TerrainType.MOUNTAIN, TerrainType.BUILDING)


def _clear(wm, x, y, w, h) -> None:
    for yy in range(y, min(wm.height, y + h)):
        for xx in range(x, min(wm.width, x + w)):
            if wm.terrain[yy][xx] not in (TerrainType.WATER, TerrainType.BRIDGE):
                wm.terrain[yy][xx] = _GRASS


def _building(world, x, y, w, h, name, kind, desc) -> Location:
    wm = world.map
    for yy in range(y, min(wm.height, y + h)):
        for xx in range(x, min(wm.width, x + w)):
            wm.terrain[yy][xx] = _BUILDING
    loc = Location(name, desc, x, y, w, h)
    loc.add_property("kind", kind)
    if kind in ("chapel", "shrine"):
        loc.add_property("type", "temple")
    world.add_location(loc)
    return loc


def _fields(wm, cx, cy, r) -> None:
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if 0 <= xx < wm.width and 0 <= yy < wm.height \
                    and wm.terrain[yy][xx] == _GRASS \
                    and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                if (xx + yy) % 2 == 0:              # a chequer of tilled fields
                    wm.terrain[yy][xx] = _FARM


def _village_sites(wm, center, radius, seed, n=3):
    """`n` grassy sites out past the town, spread around the compass."""
    rng = random.Random(seed)
    cx, cy = center
    sites, tries = [], 0
    ring = radius + 14
    while len(sites) < n and tries < 400:
        tries += 1
        a = rng.uniform(0, 6.2832)
        r = radius + rng.randint(10, 26)
        x = int(cx + r * __import__("math").cos(a))
        y = int(cy + r * __import__("math").sin(a))
        if not (6 <= x < wm.width - 8 and 6 <= y < wm.height - 8):
            continue
        if wm.terrain[y][x] in _BLOCK:
            continue
        if any(abs(x - sx) + abs(y - sy) < 22 for sx, sy in sites):
            continue
        sites.append((x, y))
    return sites


def _build_village(world, vx, vy, name):
    wm = world.map
    _clear(wm, vx - 1, vy - 1, 9, 7)
    marker = Location(f"{name} Village",
                      f"A small farming village of thatch and hedgerow that "
                      f"sends its grain to Oakvale.", vx - 1, vy - 1, 9, 7)
    marker.add_property("village", True)
    world.add_location(marker)
    plan = [("Farmhouse", "farmhouse", 0, 0), ("Cottage", "cottage", 3, 0),
            ("Cottage", "cottage", 6, 0), ("Chapel", "chapel", 0, 3),
            ("Well", "well", 3, 3), ("Barn", "stable", 5, 3)]
    for title, kind, dx, dy in plan:
        w, h = (1, 1) if kind == "well" else (2, 2)
        _building(world, vx + dx, vy + dy, w, h, f"{name} {title}", kind,
                  f"A {kind} in {name} Village.")
    _fields(wm, vx + 4, vy + 8, 6)                 # fields south of the houses
    return {"name": name, "center": (vx + 3, vy + 2)}


def _nearest_town_edge(world, center, radius, target):
    """A gate/road tile on Oakvale's edge nearest the target village."""
    town = next((l for l in world.locations
                 if l.name == "Oakvale" and l.get_property("town")), None)
    gates = [tuple(g) for g in (town.get_property("gates") or [])] if town \
        else []
    tx, ty = target
    best = None
    for g in gates:
        d = (g[0] - tx) ** 2 + (g[1] - ty) ** 2
        if best is None or d < best[0]:
            best = (d, g)
    if best:
        return best[1]
    cx, cy = center                                # fall back to the town centre
    return (cx, cy)


def build_countryside(world, center, radius: int, seed: int = 0) -> list:
    """Plant supporting villages + farms + roads around Oakvale."""
    wm = world.map
    sites = _village_sites(wm, center, radius, seed, n=3)
    villages = []
    for i, (vx, vy) in enumerate(sites):
        name = VILLAGE_NAMES[i % len(VILLAGE_NAMES)]
        info = _build_village(world, vx, vy, name)
        villages.append(info)
        edge = _nearest_town_edge(world, center, radius, info["center"])
        road_astar.connect(wm, edge, info["center"])
    # farm belts just outside the town wall
    cx, cy = center
    for a in range(0, 360, 30):
        rad = __import__("math").radians(a)
        fx = int(cx + (radius + 5) * __import__("math").cos(rad))
        fy = int(cy + (radius + 5) * __import__("math").sin(rad))
        if 0 <= fx < wm.width and 0 <= fy < wm.height:
            _fields(wm, fx, fy, 4)
    logger.info("Countryside: %d villages + farm belts.", len(villages))
    return villages


def populate_villages(engine, villages, seed: int = 0) -> int:
    """Seat farmers + villagers in the countryside villages."""
    from world.town.population import _seat, _klass, _free_tile_in
    n = 0
    for v in villages:
        name = v["name"]
        for loc in engine.world.locations:
            if not loc.get_property("kind"):
                continue
            if not loc.name.startswith(name + " "):
                continue
            kind = loc.get_property("kind")
            if kind == "well":
                continue
            role = "Farmer" if kind in ("farmhouse", "cottage") else \
                ("Chaplain" if kind == "chapel" else "Villager")
            klass = "cleric" if kind == "chapel" else "villager"
            _seat(engine, _klass(klass), role, loc.name, _free_tile_in(engine, loc))
            n += 1
    logger.info("Seated %d villagers across the countryside.", n)
    return n
