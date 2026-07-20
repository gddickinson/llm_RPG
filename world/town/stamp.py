"""OAKVALE T5 — stamp a `TownPlan` onto the world map.

Turns the pure geometry of a `town_gen.TownPlan` into real terrain + `Location`s:
the town disc is cleared to grass (rivers kept), streets become ROAD (a BRIDGE
where a road must cross water), the core wall becomes WALL (BUILDING) with its
gates left as ROAD, and every building lot becomes a BUILDING footprint + a
`Location` carrying its `kind` (which the 2.5D renderer + interior/shop systems
read) and a `type` tag. A town-marker `Location` records the gates + towers (so
`town_gates`/`fortify`/`tower_defense` can defend it). Names are unique per
building (evocative naming + keepers come with T6 population).
"""

from world.location import Location
from world.world_map import TerrainType

_ROAD, _BUILDING = TerrainType.ROAD, TerrainType.BUILDING
_WATER, _BRIDGE, _GRASS = TerrainType.WATER, TerrainType.BRIDGE, TerrainType.GRASS

# building KIND → the Location `type` tag the interior/shop/presence systems key on
_TYPE = {
    "cathedral": "cathedral", "temple": "temple", "chapel": "temple",
    "shrine": "temple", "tavern": "tavern", "inn": "tavern", "forge": "forge",
    "smithy": "forge", "armoury": "forge", "shop": "shop", "stall": "shop",
    "bakery": "shop", "bank": "shop", "hall": "hall", "guildhall": "guildhall",
    "library": "library",
}
_KIND_TITLE = {
    "tavern": "Tavern", "inn": "Inn", "smithy": "Smithy", "forge": "Forge",
    "armoury": "Armoury", "shop": "Shop", "bakery": "Bakery",
    "library": "Library", "guildhall": "Guildhall", "temple": "Temple",
    "chapel": "Chapel", "shrine": "Shrine", "home": "House",
    "cottage": "Cottage", "farmhouse": "Farmhouse", "stable": "Stable",
    "warehouse": "Warehouse", "granary": "Granary", "mill": "Mill",
    "sawmill": "Sawmill", "workshop": "Workshop", "tower": "Tower",
    "stall": "Market Stall", "well": "Well", "storage": "Storehouse",
    "watchtower": "Watchtower", "bank": "Bank",
}
_LANDMARKS = {"cathedral": "{t} Cathedral", "hall": "{t} Town Hall",
              "bank": "{t} Bank"}


def _inb(wm, x, y) -> bool:
    return 0 <= x < wm.width and 0 <= y < wm.height


def clear_disc(wm, cx, cy, radius) -> None:
    """Clear the town disc to grass, keeping water (so rivers → bridges)."""
    for y in range(int(cy - radius), int(cy + radius) + 1):
        for x in range(int(cx - radius), int(cx + radius) + 1):
            if _inb(wm, x, y) and (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                if wm.terrain[y][x] not in (_WATER, _BRIDGE):
                    wm.terrain[y][x] = _GRASS


def _building_name(lot, town, counters) -> str:
    if lot.kind in _LANDMARKS and counters.get(lot.kind, 0) == 0:
        counters[lot.kind] = 1
        return _LANDMARKS[lot.kind].format(t=town)
    n = counters.get(lot.kind, 0) + 1
    counters[lot.kind] = n
    return f"{town} {_KIND_TITLE.get(lot.kind, lot.kind.title())} {n}"


def _building_desc(lot) -> str:
    return f"A {lot.kind.replace('_', ' ')} in the {lot.district} district " \
           f"of the town."


def _stamp_buildings(world, plan, town_name):
    wm = world.map
    counters, locs = {}, []
    for lot in plan.lots:
        for (x, y) in lot.tiles():
            if _inb(wm, x, y):
                wm.terrain[y][x] = _BUILDING
        loc = Location(_building_name(lot, town_name, counters),
                       _building_desc(lot), lot.x, lot.y, lot.w, lot.h)
        loc.add_property("kind", lot.kind)
        loc.add_property("district", lot.district)
        tag = _TYPE.get(lot.kind)
        if tag:
            loc.add_property("type", tag)
        if lot.kind in ("forge", "smithy", "armoury"):
            loc.add_property("forge", True)
        world.add_location(loc)
        locs.append(loc)
    return locs


def stamp_town(world, plan, name: str = "Oakvale", clear: bool = True) -> dict:
    """Stamp a TownPlan's streets, wall, gates and buildings onto the world."""
    wm = world.map
    if clear:
        clear_disc(wm, plan.cx, plan.cy, plan.radius)
    for (x, y), _kind in plan.streets.road_tiles().items():
        if _inb(wm, x, y):
            wm.terrain[y][x] = _BRIDGE if wm.terrain[y][x] == _WATER else _ROAD
    for (x, y) in plan.wall.wall:
        if _inb(wm, x, y) and wm.terrain[y][x] != _ROAD:
            wm.terrain[y][x] = _BUILDING
    for (x, y) in plan.wall.gates:                     # gates stay passable
        if _inb(wm, x, y):
            wm.terrain[y][x] = _ROAD
    locs = _stamp_buildings(world, plan, name)
    tx = int(plan.cx - plan.radius)
    ty = int(plan.cy - plan.radius)
    town = Location(name, "A great walled town of many districts.", tx, ty,
                    int(2 * plan.radius), int(2 * plan.radius))
    town.add_property("gates", [list(g) for g in plan.wall.gates])
    town.add_property("towers", [list(t) for t in plan.wall.towers])
    town.add_property("town", True)
    world.add_location(town)
    return {"name": name, "buildings": len(locs),
            "gates": len(plan.wall.gates), "towers": len(plan.wall.towers)}
