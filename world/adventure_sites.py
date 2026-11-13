"""Where an authored adventure's areas go on the map (shared by engine/adventure_seed, adventure_tome, ravenmoor).

The seeders used to take the FIRST suitable tile scanning row by row from (1,1), so every adventure's areas
piled up side by side along the top edge, and a "swamp" adventure on a map with no swamp fell back to the
first free tile. Now `pick_site`:

- collects every open candidate tile (not building/water/mountain, no one standing there, outside every
  named place, at least `min_dist` from the player start) on or beside the wanted terrain;
- keeps candidates at least `SPACING` from this adventure's own areas and `ADV_SPACING` from every OTHER
  adventure's areas, and prefers ones within `CLUSTER` of this adventure's first area (so an adventure's
  places stay a journey apart but in one region);
- chooses one with a seeded RNG (derived from the global `random`, so a seeded GameEngine is reproducible);
- for wetland terrain (swamp) with no swamp on the map, falls back to a water shore, and failing that
  paints a small marsh around a chosen open tile;
- relaxes the spacing rules step by step before giving up.
"""
import random
from typing import Iterable, List, Optional, Set, Tuple

from world.world_map import TerrainType

BAD = (TerrainType.BUILDING, TerrainType.WATER, TerrainType.MOUNTAIN)
SPACING = 6          # between areas of one adventure
ADV_SPACING = 12     # from any other adventure's area
CLUSTER = 45         # prefer later areas within this of the adventure's first area
MARSH_RADIUS = 2
_N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
# terrain to try, in order, when an adventure wants this one
FALLBACK = {TerrainType.SWAMP: (TerrainType.SWAMP, TerrainType.WATER)}
_PAINTABLE = (TerrainType.GRASS, TerrainType.FOREST, TerrainType.FARMLAND)


def _dist(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _place_tiles(engine) -> Set[Tuple[int, int]]:
    """Every tile inside a named place (what `world.get_location_at` would report)."""
    out = set()
    for loc in engine.world.locations:
        for y in range(loc.y, loc.y + max(1, loc.height)):
            for x in range(loc.x, loc.x + max(1, loc.width)):
                out.add((x, y))
    return out


def _other_adventure_areas(engine, used: Iterable) -> List[Tuple[int, int]]:
    mine = set(map(tuple, used))
    return [(l.x, l.y) for l in engine.world.locations
            if (l.properties or {}).get("adventure") and (l.x, l.y) not in mine]


def _touches(wmap, x, y, terrain) -> bool:
    if wmap.terrain[y][x] == terrain:
        return True
    return any(0 <= x + dx < wmap.width and 0 <= y + dy < wmap.height and wmap.terrain[y + dy][x + dx] == terrain
               for dx, dy in _N4)


def paint_marsh(wmap, centre, taken: Set[Tuple[int, int]], radius: int = MARSH_RADIUS) -> int:
    """Turn open ground around `centre` into SWAMP (never a named place, road or occupied tile). Returns tiles painted."""
    cx, cy = centre
    n = 0
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if not (0 <= x < wmap.width and 0 <= y < wmap.height) or (x, y) in taken or (x, y) in wmap.characters:
                continue
            if _dist((x, y), centre) <= radius and wmap.terrain[y][x] in _PAINTABLE:
                wmap.set_terrain(x, y, TerrainType.SWAMP)
                n += 1
    return n


def pick_site(engine, near: str, used, min_dist: int, rng: Optional[random.Random] = None) -> Optional[Tuple[int, int]]:
    """An open tile for one adventure area of `near` terrain (see the module docstring), or None if the map is full."""
    rng = rng or random.Random(random.getrandbits(64))
    wmap = engine.world.map
    try:
        start = tuple(engine.player.position)
    except Exception:
        start = (wmap.width // 2, wmap.height // 2)
    want = getattr(TerrainType, near.upper(), TerrainType.GRASS)
    used = [tuple(p) for p in used]
    taken = _place_tiles(engine)
    others = _other_adventure_areas(engine, used)
    free = [(x, y) for y in range(1, wmap.height - 1) for x in range(1, wmap.width - 1)
            if wmap.terrain[y][x] not in BAD and (x, y) not in wmap.characters and (x, y) not in taken
            and (x, y) not in used and _dist((x, y), start) >= min_dist]
    if not free:
        return None

    def spaced(p, own=SPACING, other=ADV_SPACING):
        return all(_dist(p, u) >= own for u in used) and all(_dist(p, o) >= other for o in others)

    def choose(cands):
        if used:
            close = [p for p in cands if _dist(p, used[0]) <= CLUSTER]
            cands = close or cands
        return rng.choice(cands) if cands else None

    for terrain in FALLBACK.get(want, (want,)):
        pick = choose([p for p in free if spaced(p) and _touches(wmap, p[0], p[1], terrain)])
        if pick:
            return pick
    if want in FALLBACK:                       # no wetland at all: make a little marsh
        pick = choose([p for p in free if spaced(p) and wmap.terrain[p[1]][p[0]] in _PAINTABLE])
        if pick:
            paint_marsh(wmap, pick, taken)
            return pick
    for own, other in ((SPACING, 0), (1, 0)):  # relax the spacing before giving up
        pick = choose([p for p in free if spaced(p, own, other) and _touches(wmap, p[0], p[1], want)]) or \
            choose([p for p in free if spaced(p, own, other)])
        if pick:
            return pick
    return rng.choice(free)
