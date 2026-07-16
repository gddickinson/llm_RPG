"""OAKVALE T4 — BUILDING LOTS: landmarks, street frontage, interior fill.

Three passes seat the town's buildings, each a `BuildingLot` rectangle (a future
`Location`), placed by its WARD (T1 `DistrictPlan` → a building KIND from
`data/town/districts.json`), rejected if it leaves the disc or overlaps a
street/plaza/wall/another lot:

1. **Landmarks** — the town's grand singletons are placed FIRST so they always
   exist and get room: a cathedral + a temple in the sacred ward, a town hall +
   bank in the civic core, guildhalls + libraries in the guild ward, inns +
   taverns in the commercial ward, an armoury in the metal-craft ward.
2. **Frontage** — walk each street's centre-line seating lots set back on both
   sides (buildings front the street, medieval-town style), densely.
3. **Interior fill** — scatter district-appropriate buildings into the pockets
   between streets so the town reads full, not just street-lined.

Adapted from `autonomous_world`'s `plan_building_lots` + `lot_subdivision`. Pure
+ deterministic; headless-testable.
"""

import math
import random
from typing import Dict, List, Tuple

from world.town.streets import _line_tiles

# footprint (w, h) per building KIND — grand civic/sacred buildings are largest
_SIZE = {
    "cathedral": (6, 5), "hall": (5, 4), "temple": (4, 4), "guildhall": (4, 3),
    "library": (3, 3), "inn": (3, 3), "warehouse": (3, 3), "granary": (3, 3),
    "bank": (3, 3), "tavern": (3, 2), "stable": (3, 2), "tower": (2, 3),
    "watchtower": (2, 3), "shop": (2, 2), "smithy": (2, 2), "forge": (2, 2),
    "armoury": (2, 2), "bakery": (2, 2), "workshop": (2, 2), "mill": (2, 2),
    "sawmill": (2, 2), "chapel": (2, 2), "storage": (2, 2), "home": (2, 2),
    "cottage": (2, 2), "farmhouse": (2, 2), "shrine": (1, 1), "stall": (1, 1),
    "well": (1, 1),
}

# grand buildings guaranteed a spot, each in a ward of a preferred type
_LANDMARKS: List[Tuple[str, Tuple[str, ...]]] = [
    ("cathedral", ("temple",)),
    ("temple", ("temple", "civic")),
    ("hall", ("civic", "market")),
    ("bank", ("civic", "market")),
    ("guildhall", ("guild", "civic")),
    ("guildhall", ("guild", "commercial")),
    ("library", ("guild", "civic")),
    ("library", ("civic", "commercial")),
    ("inn", ("commercial", "market")),
    ("inn", ("commercial",)),
    ("tavern", ("commercial", "market")),
    ("tavern", ("commercial",)),
    ("tavern", ("residential",)),
    ("armoury", ("craft_metal",)),
    ("tower", ("guild", "civic")),
]


def building_size(kind: str) -> Tuple[int, int]:
    return _SIZE.get(kind, (2, 2))


def _district_buildings() -> Dict[str, list]:
    from items.data_loader import load_data_file
    try:
        return (load_data_file("town/districts.json") or {}).get(
            "district_buildings", {})
    except Exception:                                # pragma: no cover
        return {}


class BuildingLot:
    __slots__ = ("x", "y", "w", "h", "kind", "district")

    def __init__(self, x, y, w, h, kind, district):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.kind, self.district = kind, district

    def tiles(self):
        return [(self.x + dx, self.y + dy)
                for dy in range(self.h) for dx in range(self.w)]

    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    def __repr__(self):
        return f"Lot({self.kind}@{self.x},{self.y} {self.w}x{self.h})"


def _perp(x1, y1, x2, y2) -> Tuple[float, float]:
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1.0
    return (-dy / L, dx / L)


def _fits(x0, y0, w, h, claimed, cx, cy, radius) -> bool:
    for yy in range(y0, y0 + h):
        for xx in range(x0, x0 + w):
            if (xx, yy) in claimed:
                return False
            if (xx - cx) ** 2 + (yy - cy) ** 2 > radius * radius:
                return False
    return True


def _claim(x0, y0, w, h, claimed) -> None:
    """Claim a footprint plus a one-tile yard gap so lots never fuse."""
    for dy in range(-1, h + 1):
        for dx in range(-1, w + 1):
            claimed.add((x0 + dx, y0 + dy))


def _pick_kind(district, buildings, rng):
    pool = buildings.get(district)
    return rng.choice(pool) if pool else None


def _place_landmarks(dp, claimed, rng) -> List[BuildingLot]:
    # the defended core, as a fallback so a landmark is placed even when its
    # ideal ward type didn't appear this seed (a cathedral is GUARANTEED)
    inner = [xy for xy in dp.ward_map if dp.ring_at(*xy) == "inner"]
    lots = []
    for kind, prefs in _LANDMARKS:
        w, h = building_size(kind)
        cands = []
        for pref in prefs:
            cands.extend(dp.tiles_of_type(pref))
        if not cands:
            cands = list(inner)          # place it somewhere in the core
        if not cands:
            continue
        rng.shuffle(cands)
        for (cxp, cyp) in cands[:600]:
            x0, y0 = cxp - w // 2, cyp - h // 2
            if _fits(x0, y0, w, h, claimed, dp.cx, dp.cy, dp.radius):
                _claim(x0, y0, w, h, claimed)
                lots.append(BuildingLot(x0, y0, w, h, kind,
                                        dp.type_at(cxp, cyp) or prefs[0]))
                break
    return lots


def _place_frontage(dp, sp, claimed, buildings, rng, setback=2) -> List[BuildingLot]:
    lots = []
    for seg in sp.segments:
        if seg.kind == "plaza":
            continue
        line = _line_tiles(seg.x1, seg.y1, seg.x2, seg.y2)
        if len(line) < 3:
            continue
        px, py = _perp(seg.x1, seg.y1, seg.x2, seg.y2)
        i = 2
        while i < len(line) - 2:
            sx, sy = line[i]
            for side in (1, -1):
                icx = int(round(sx + px * side * setback))
                icy = int(round(sy + py * side * setback))
                dtype = dp.type_at(icx, icy)
                if dtype is None:
                    continue
                kind = _pick_kind(dtype, buildings, rng)
                if kind is None:
                    continue
                w, h = building_size(kind)
                x0, y0 = icx - w // 2, icy - h // 2
                if _fits(x0, y0, w, h, claimed, dp.cx, dp.cy, dp.radius):
                    _claim(x0, y0, w, h, claimed)
                    lots.append(BuildingLot(x0, y0, w, h, kind, dtype))
            i += rng.randint(1, 2)
    return lots


def _fill_interior(dp, claimed, buildings, rng, prob=0.55) -> List[BuildingLot]:
    lots = []
    cx, cy, r = dp.cx, dp.cy, dp.radius
    for cyp in range(int(cy - r), int(cy + r) + 1, 3):
        for cxp in range(int(cx - r), int(cx + r) + 1, 3):
            dtype = dp.type_at(cxp, cyp)
            if dtype is None or rng.random() > prob:
                continue
            kind = _pick_kind(dtype, buildings, rng)
            if kind is None:
                continue
            w, h = building_size(kind)
            x0, y0 = cxp - w // 2, cyp - h // 2
            if _fits(x0, y0, w, h, claimed, cx, cy, r):
                _claim(x0, y0, w, h, claimed)
                lots.append(BuildingLot(x0, y0, w, h, kind, dtype))
    return lots


def place_lots(district_plan, street_plan, core_wall=None, seed: int = 0,
               setback: int = 2) -> List[BuildingLot]:
    """Seat the town's buildings: landmarks → street frontage → interior fill."""
    rng = random.Random(seed)
    buildings = _district_buildings()
    claimed = set(street_plan.road_tiles().keys())
    claimed |= set(street_plan.square_tiles())
    if core_wall is not None:
        claimed |= set(core_wall.wall)
    lots = _place_landmarks(district_plan, claimed, rng)
    lots += _place_frontage(district_plan, street_plan, claimed, buildings,
                            rng, setback)
    lots += _fill_interior(district_plan, claimed, buildings, rng)
    return lots


def district_counts(lots: List[BuildingLot]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for lot in lots:
        out[lot.kind] = out.get(lot.kind, 0) + 1
    return out
