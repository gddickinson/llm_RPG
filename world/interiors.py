"""Building interiors.

Each building location can have an Interior (mini-map) with its own
terrain grid, furniture, and NPC placements. The player "enters" by
stepping onto a building tile and pressing the interact key.

Interiors are owned by the World and keyed by location name. When the
player is inside an interior, `engine.current_interior` is set; the
renderer can switch to drawing the interior tile grid instead of the
outdoor map.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.interiors")


@dataclass
class Interior:
    """A small indoor map for a building."""
    name: str
    width: int = 8
    height: int = 6
    terrain: List[List[TerrainType]] = field(default_factory=list)
    door: Tuple[int, int] = (4, 5)        # exit tile
    npc_spots: List[Tuple[int, int]] = field(default_factory=list)
    furniture: List[Dict] = field(default_factory=list)
    description: str = ""
    # Multi-level buildings (P9A.5): linked level stack
    ground: bool = True
    stairs_up: Optional[Tuple[int, int]] = None
    stairs_down: Optional[Tuple[int, int]] = None
    level_above: Optional["Interior"] = None
    level_below: Optional["Interior"] = None

    def init_grid(self) -> None:
        """Build the wall/floor grid and cut the current door."""
        if not self.terrain:
            self.terrain = [
                [TerrainType.GRASS for _ in range(self.width)]
                for _ in range(self.height)
            ]
            for x in range(self.width):
                self.terrain[0][x] = TerrainType.BUILDING
                self.terrain[self.height - 1][x] = TerrainType.BUILDING
            for y in range(self.height):
                self.terrain[y][0] = TerrainType.BUILDING
                self.terrain[y][self.width - 1] = TerrainType.BUILDING
        self._cut_door()

    def _cut_door(self) -> None:
        dx, dy = self.door
        if 0 <= dx < self.width and 0 <= dy < self.height:
            self.terrain[dy][dx] = TerrainType.ROAD


def _make(name: str, width: int, height: int, description: str,
          door: Tuple[int, int],
          furniture: List[Dict],
          npc_spots: List[Tuple[int, int]]) -> Interior:
    inter = Interior(name=name, width=width, height=height,
                     description=description, door=door)
    inter.furniture = list(furniture)
    inter.npc_spots = list(npc_spots)
    inter.init_grid()
    return inter


def make_tavern_interior() -> Interior:
    return _make(
        name="Oakvale Tavern (interior)",
        width=10, height=7,
        description="Warm light, the smell of ale, a bard tuning a lute.",
        door=(5, 6),
        furniture=[
            {"name": "Bar", "x": 2, "y": 1},
            {"name": "Hearth", "x": 8, "y": 1},
            {"name": "Table", "x": 4, "y": 3},
            {"name": "Table", "x": 6, "y": 3},
            {"name": "Bed", "x": 8, "y": 5},
            {"name": "Barrel", "x": 1, "y": 1},
            {"name": "Stairs up", "x": 1, "y": 5},
        ],
        npc_spots=[(2, 2), (5, 3), (6, 3)],
    )


def make_forge_interior() -> Interior:
    return _make(
        name="Durgan's Forge (interior)",
        width=9, height=6,
        description="Heat from the anvil. Sparks fly with every hammer blow.",
        door=(4, 5),
        furniture=[
            {"name": "Anvil", "x": 4, "y": 2},
            {"name": "Forge", "x": 6, "y": 1},
            {"name": "Workbench", "x": 2, "y": 3},
            {"name": "Wall rack", "x": 7, "y": 3},
        ],
        npc_spots=[(4, 3)],
    )


def make_shop_interior() -> Interior:
    return _make(
        name="General Store (interior)",
        width=8, height=6,
        description="Shelves stacked with goods and curiosities.",
        door=(4, 5),
        furniture=[
            {"name": "Counter", "x": 4, "y": 1},
            {"name": "Shelves", "x": 1, "y": 1},
            {"name": "Shelves", "x": 6, "y": 1},
            {"name": "Crates", "x": 3, "y": 3},
        ],
        npc_spots=[(4, 2)],
    )


def make_temple_interior() -> Interior:
    return _make(
        name="Temple of Light (interior)",
        width=8, height=7,
        description="Sunlight streams through stained glass.",
        door=(4, 6),
        furniture=[
            {"name": "Altar", "x": 4, "y": 1},
            {"name": "Pew", "x": 2, "y": 3},
            {"name": "Pew", "x": 5, "y": 3},
            {"name": "Statue", "x": 1, "y": 2},
            {"name": "Statue", "x": 6, "y": 2},
        ],
        npc_spots=[(4, 2)],
    )


def make_default_interior(name: str) -> Interior:
    return _make(
        name=f"{name} (interior)",
        width=8, height=6,
        description="A simple interior.",
        door=(4, 5),
        furniture=[
            {"name": "Bed", "x": 1, "y": 1},
            {"name": "Hearth", "x": 6, "y": 1},
            {"name": "Chest", "x": 1, "y": 3},
            {"name": "Chair", "x": 5, "y": 3},
        ],
        npc_spots=[],
    )


def _furnish_rooms(inter, rooms, seed, kind="") -> None:
    """BLD.2: furnish a subdivided interior by ROOM FUNCTION — each leaf is
    tagged a room_type from the building's room-set and gets that type's kit
    (`world/room_plan.py`), so a tavern reads common-room + bar + kitchen and a
    smithy forge + workshop, not a size-ranked bed-and-chest in every room."""
    from world import room_plan
    room_plan.furnish_typed(inter, rooms, kind, seed)


def make_from_blueprint(loc_name: str, bp) -> Interior:
    """Build an Interior from a Blueprint grid.

    Maps blueprint cells (W/F/D/T/B/A/C/P/R/S) to terrain + furniture.
    """
    name = f"{loc_name} (interior)"
    w, h = bp.width, bp.height
    inter = Interior(name=name, width=w, height=h,
                     description=bp.description)
    # Pre-fill terrain
    inter.terrain = [[TerrainType.GRASS for _ in range(w)] for _ in range(h)]
    door_pos = None
    for y in range(h):
        for x in range(w):
            cell = bp.cell(x, y)
            if cell == "W":
                inter.terrain[y][x] = TerrainType.BUILDING
            elif cell == "D":
                inter.terrain[y][x] = TerrainType.ROAD
                door_pos = (x, y)
            elif cell in ("F", "."):
                pass  # grass / floor
            else:
                # Furniture: keep cell walkable (interior floor) but record
                # the furniture object.
                inter.terrain[y][x] = TerrainType.GRASS
                cell_name_map = {
                    "T": "Table", "B": "Bed", "A": "Anvil",
                    "C": "Chest", "P": "Hearth", "R": "Barrel",
                    "S": "Altar",
                }
                if getattr(bp, "kind", "") == "library":
                    cell_name_map["R"] = "Shelves"
                if getattr(bp, "kind", "") == "well":
                    cell_name_map["S"] = "Well"
                inter.furniture.append({
                    "name": cell_name_map.get(cell, "Furniture"),
                    "x": x, "y": y,
                })
    if door_pos is None:
        door_pos = (w // 2, h - 1)
        if 0 <= door_pos[1] < h:
            inter.terrain[door_pos[1]][door_pos[0]] = TerrainType.ROAD
    inter.door = door_pos
    # NPC spot near the center (off-furniture)
    spot = (w // 2, h // 2)
    inter.npc_spots = [spot]
    return inter


def fit_to_footprint(inter: Interior, loc) -> Interior:
    """P9A.7b: the inside matches the outside. Interior dimensions
    scale with the building's overworld footprint (a hut opens into a
    hut, a hall into a hall), the interior door sits at the south-face
    center — the same edge as the exterior door glyph — and furniture
    keeps its relative layout, remapped proportionally."""
    # GX.3 SCALE-UP (George: "the scale of everything feels small and cramped").
    # A ×4 footprint multiplier + far bigger caps, so a 2×2 building opens into a
    # roomy 10×10 (was 8×8) and a large footprint yields a genuinely big hall —
    # room enough for a church nave to seat scores. Small buildings stay modest.
    tw = max(7, min(28, loc.width * 4 + 2))
    th = max(6, min(22, loc.height * 4 + 2))
    old_w, old_h = inter.width, inter.height

    def remap(x: int, y: int) -> Tuple[int, int]:
        nx = 1 + round((x - 1) * (tw - 3) / max(1, old_w - 3))
        ny = 1 + round((y - 1) * (th - 3) / max(1, old_h - 3))
        return (max(1, min(tw - 2, nx)), max(1, min(th - 2, ny)))

    # Fresh shell: walls around floor, door at south-center
    inter.width, inter.height = tw, th
    inter.terrain = [[TerrainType.GRASS for _ in range(tw)]
                     for _ in range(th)]
    for x in range(tw):
        inter.terrain[0][x] = TerrainType.BUILDING
        inter.terrain[th - 1][x] = TerrainType.BUILDING
    for y in range(th):
        inter.terrain[y][0] = TerrainType.BUILDING
        inter.terrain[y][tw - 1] = TerrainType.BUILDING
    inter.door = (tw // 2, th - 1)
    inter.terrain[th - 1][tw // 2] = TerrainType.ROAD

    # BLD.2: a building whose function has a MULTI-ROOM program becomes multi-
    # room (BSP subdivision + functional room typing); a single-room building
    # (a well) or a tiny footprint stays one open room so its layout survives.
    kind = loc.get_property("type", "") if hasattr(loc, "get_property") else ""
    from world import room_plan
    room_set = room_plan.room_set_for(kind)
    # subdivide when the building's FUNCTION wants ≥2 rooms (a small tavern still
    # gets a common-room + bar), OR its footprint is simply big enough (a large
    # building is multi-room whatever its kind); a tiny kindless hut stays open.
    has_program = len(room_set) >= 2
    big_footprint = tw >= 11 and th >= 8
    if (has_program and tw >= 8 and th >= 7) or big_footprint:
        from world import room_gen
        seed = sum(ord(c) for c in inter.name) + old_w * 7 + old_h * 13
        # min_room=2 so a medium building (8x8 → 6x6 inner) still splits; depth
        # scales with footprint so a small building gets a couple of rooms, not
        # a warren of 1-tile closets
        big = tw >= 12 and th >= 10
        depth = 3 if (big and len(room_set) > 3) else 2
        grid, rooms = room_gen.subdivide(tw, th, seed,
                                         min_room=2, max_depth=depth)
        grid[th - 2][tw // 2] = room_gen.FLOOR       # keep the entrance clear
        for y in range(th - 1):
            for x in range(1, tw - 1):
                if grid[y][x] == room_gen.WALL:
                    inter.terrain[y][x] = TerrainType.BUILDING
        inter.terrain[th - 1][tw // 2] = TerrainType.ROAD
        _furnish_rooms(inter, rooms, seed, kind)
        return inter

    # Remap furniture, nudging collisions to the next free tile
    taken = {inter.door}
    moved = []
    for piece in inter.furniture:
        spot = remap(piece.get("x", 1), piece.get("y", 1))
        if spot in taken:
            spot = next((t for t in _inner_tiles(tw, th)
                         if t not in taken), spot)
        taken.add(spot)
        piece["x"], piece["y"] = spot
        moved.append(piece)
    inter.furniture = moved
    inter.npc_spots = [remap(x, y) for x, y in inter.npc_spots]
    return inter


def _inner_tiles(w: int, h: int) -> List[Tuple[int, int]]:
    return [(x, y) for y in range(1, h - 1) for x in range(1, w - 1)]


def _free_tiles(inter: Interior) -> List[Tuple[int, int]]:
    """Inner floor tiles with no wall, door, or furniture on them."""
    taken = {(f.get("x"), f.get("y")) for f in inter.furniture}
    taken.add(inter.door)
    out = []
    for y in range(1, inter.height - 1):
        for x in range(1, inter.width - 1):
            if inter.terrain[y][x] == TerrainType.BUILDING:
                continue
            if (x, y) in taken:
                continue
            out.append((x, y))
    return out


def add_upper_floor(inter: Interior) -> Optional[Interior]:
    """Bedrooms above the taproom (P9A.5). Clean transitions: the
    stair tile on each level carries you to its twin on the other."""
    free = _free_tiles(inter)
    if not free:
        return None
    spot = free[-1]                      # a corner, away from the door
    loft = Interior(name=f"{inter.name} — upstairs",
                    width=inter.width, height=inter.height,
                    door=spot, ground=False,
                    description="Creaking boards, low beams, and the "
                                "quiet of the bedrooms.")
    loft.init_grid()
    loft.stairs_down = spot
    loft.furniture.append({"name": "Stairs down",
                           "x": spot[0], "y": spot[1]})
    beds = [t for t in _free_tiles(loft) if t != spot][:3]
    for i, (bx, by) in enumerate(beds):
        loft.furniture.append(
            {"name": "Bed" if i < 2 else "Chest", "x": bx, "y": by})
    inter.stairs_up = spot
    inter.furniture.append({"name": "Stairs up",
                            "x": spot[0], "y": spot[1]})
    inter.level_above = loft
    loft.level_below = inter
    return loft


def add_cellar(inter: Interior) -> Optional[Interior]:
    """Storage below the shop floor (P9A.5)."""
    free = _free_tiles(inter)
    if not free:
        return None
    spot = free[0]
    cellar = Interior(name=f"{inter.name} — cellar",
                      width=inter.width, height=inter.height,
                      door=spot, ground=False,
                      description="Cool dark air, dust, and stacked "
                                  "stores.")
    cellar.init_grid()
    cellar.stairs_up = spot
    cellar.furniture.append({"name": "Stairs up",
                             "x": spot[0], "y": spot[1]})
    stock = [t for t in _free_tiles(cellar) if t != spot][:3]
    for i, (bx, by) in enumerate(stock):
        cellar.furniture.append(
            {"name": "Barrel" if i < 2 else "Chest",
             "x": bx, "y": by})
    inter.stairs_down = spot
    inter.furniture.append({"name": "Stairs down",
                            "x": spot[0], "y": spot[1]})
    inter.level_below = cellar
    cellar.level_above = inter
    return cellar


def build_interiors_for_world(world) -> Dict[str, Interior]:
    """Create matching interiors for each building in the world.

    Tries the blueprint library first; falls back to the old factory set.
    """
    try:
        from world.blueprints import blueprint_for_location
    except Exception:
        blueprint_for_location = None

    interiors: Dict[str, Interior] = {}
    for loc in world.locations:
        ltype = loc.get_property("type", "")
        name_l = loc.name.lower()
        inter = None

        # Try blueprint first
        bp = None
        if blueprint_for_location is not None:
            bp = blueprint_for_location(loc.name)
            if bp is not None:
                inter = make_from_blueprint(loc.name, bp)

        # Fallback to hand-built interior factories
        if inter is None:
            if "tavern" in name_l:
                inter = make_tavern_interior()
            elif "forge" in name_l or "smith" in name_l:
                inter = make_forge_interior()
            elif "store" in name_l or "shop" in name_l:
                inter = make_shop_interior()
            elif ("temple" in name_l or "shrine" in name_l
                    or "cathedral" in name_l or "church" in name_l):
                inter = make_temple_interior()   # GX.4 rescaled to a big nave
            elif ltype in ("tavern", "shop", "temple", "forge", "cathedral"):
                inter = make_default_interior(loc.name)
            else:
                continue

        # The inside matches the outside (P9A.7b)
        try:
            fit_to_footprint(inter, loc)
        except Exception as e:
            logger.debug(f"footprint fit for {loc.name}: {e}")
        try:   # P39.3 decorate it in-theme (braziers, pillars, rugs, …);
            from world.furnishings import furnish   # BLD.1 kind-aware fallback
            furnish(inter, loc.name, kind=(getattr(bp, "kind", None) or ltype))
        except Exception as e:
            logger.debug(f"furnish {loc.name}: {e}")
        try:   # BLD.6 atmosphere: wall torches (light pools) + hearthrugs
            from world.furnish_features import decorate_pass
            decorate_pass(inter, seed=sum(ord(c) for c in loc.name))
        except Exception as e:
            logger.debug(f"decorate {loc.name}: {e}")
        interiors[loc.name] = inter

    # Multi-level pass (P9A.5): bedrooms above taverns and inns,
    # storage cellars below shops and forges
    for name, inter in interiors.items():
        low = name.lower()
        try:
            if "tavern" in low or "inn" in low:
                add_upper_floor(inter)
            elif any(k in low for k in ("store", "goods", "shop",
                                        "smithy", "forge")):
                add_cellar(inter)
        except Exception as e:
            logger.debug(f"level stack for {name}: {e}")
    return interiors
